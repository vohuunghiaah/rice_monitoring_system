"""Deterministic temporal mosaics on a common equal-area grid."""
from contextlib import ExitStack
from datetime import date
import json
import math
import os
from pathlib import Path
import tempfile
import time

import numpy as np
import psutil
from pyproj import CRS, Transformer
import rasterio
from rasterio.transform import Affine
from rasterio.windows import Window

from src.core.spatial import load_polygons, pixel_centers, polygon_mask, sample_nearest
from src.io.downloader import SentinelDownloader
from src.viz.heatmap_generator import ndvi_to_rgb


def observation_date(value):
    if not isinstance(value, str):
        raise ValueError('Each scene needs an acquisition datetime; reprocess with --acquired-at or a manifest')
    return date.fromisoformat(value[:10])


def mosaic_scenes(summaries, output_dir, target_date, max_day_gap=3, resolution=10,
                  aoi=None, rice_mask=None, rice_class=1, chunk_size=512,
                  max_pixels=500_000_000):
    """EPSG:6933 equal-area output, closest date -> cloud -> ID, first valid wins.

    Every destination pixel has exactly one winner. No averaging across dates.
    Pixel-center polygon membership is deterministic; boundary area is an
    approximation at the requested output resolution, not a surveyed area.
    """
    target = date.fromisoformat(target_date)
    if (not math.isfinite(resolution) or resolution <= 0 or max_day_gap < 0
            or not 1 <= chunk_size <= 2048 or max_pixels < 1):
        raise ValueError('Invalid resolution, date gap, chunk size, or pixel budget')
    selected, excluded, seen = [], [], set()
    for path in summaries:
        path = Path(path)
        info = json.loads(path.read_text(encoding='utf-8-sig'))
        acquired = observation_date(info.get('datetime'))
        gap = abs((acquired-target).days)
        ndvi = Path(info['ndvi'])
        if not ndvi.is_absolute():
            ndvi = path.parent/ndvi
        ndvi = ndvi.resolve()
        if ndvi in seen:
            continue
        seen.add(ndvi)
        if gap > max_day_gap:
            excluded.append(info['scene_id'])
            continue
        cloud = info.get('cloud_cover')
        cloud = 100 if cloud is None else float(cloud)
        if not math.isfinite(cloud) or not 0 <= cloud <= 100:
            raise ValueError('Invalid source cloud cover')
        selected.append((gap, cloud, info['scene_id'], str(ndvi), info['datetime']))
    if not selected:
        raise ValueError('No input scene falls within the target date tolerance')
    selected.sort()
    if len(selected) > 128:
        raise ValueError('At most 128 source rasters per mosaic; partition the AOI')
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    polygons = load_polygons(aoi) if aoi else None
    destination = CRS.from_epsg(6933)
    to_lonlat = Transformer.from_crs(destination, 4326, always_xy=True)
    started = time.perf_counter()
    peak = psutil.Process().memory_info().rss
    valid_count, roi_count, total = 0, 0, 0.0
    aoi_count, unknown_mask_count = 0, 0
    minimum, maximum = math.inf, -math.inf
    counts = [0]*len(selected)
    with tempfile.TemporaryDirectory(dir=output, prefix='.mosaic-') as work:
        work = Path(work)
        with rasterio.Env(GDAL_CACHEMAX=32*1024**2, GDAL_TIFF_INTERNAL_MASK=True), ExitStack() as stack:
            datasets, transformers, bounds = [], [], []
            for _, _, _, path, _ in selected:
                ds = stack.enter_context(rasterio.open(path))
                if ds.crs is None or ds.count != 1:
                    raise ValueError('Mosaic inputs must be georeferenced single-band NDVI')
                datasets.append(ds)
                transformers.append(Transformer.from_crs(destination, ds.crs, always_xy=True))
                projection = Transformer.from_crs(ds.crs, destination, always_xy=True)
                bounds.append(projection.transform_bounds(*ds.bounds, densify_pts=41))
            left = min(b[0] for b in bounds)
            bottom = min(b[1] for b in bounds)
            right = max(b[2] for b in bounds)
            top = max(b[3] for b in bounds)
            if polygons:
                vertices = np.concatenate([r for p in polygons for r in p])
                projection = Transformer.from_crs(4326, destination, always_xy=True)
                ab = projection.transform_bounds(*vertices.min(axis=0), *vertices.max(axis=0), densify_pts=41)
                if max(left, ab[0]) >= min(right, ab[2]) or max(bottom, ab[1]) >= min(top, ab[3]):
                    raise ValueError('AOI does not intersect input extent')
                # Keep the full requested AOI, including uncovered pixels, so
                # the coverage denominator cannot hide missing observations.
                left, bottom, right, top = ab
            if not np.isfinite([left, bottom, right, top]).all() or left >= right or bottom >= top:
                raise ValueError('AOI does not intersect inputs or projection bounds are invalid')
            # Snap the lattice origin to a global multiple of resolution.
            left, top = math.floor(left/resolution)*resolution, math.ceil(top/resolution)*resolution
            width, height = math.ceil((right-left)/resolution), math.ceil((top-bottom)/resolution)
            if width*height > max_pixels:
                raise ValueError(f'Output has {width*height:,} pixels; reduce AOI/increase resolution or --max-pixels')
            transform = Affine(resolution, 0, left, 0, -resolution, top)
            mask_ds = stack.enter_context(rasterio.open(rice_mask)) if rice_mask else None
            if mask_ds and (mask_ds.crs is None or mask_ds.count != 1):
                raise ValueError('Rice mask must be georeferenced single-band categorical raster')
            mask_transformer = Transformer.from_crs(destination, mask_ds.crs, always_xy=True) if mask_ds else None
            profile = dict(driver='GTiff', width=width, height=height, transform=transform,
                           crs='EPSG:6933', tiled=True, blockxsize=256, blockysize=256,
                           compress='deflate', BIGTIFF='IF_SAFER')
            ndvi_out = stack.enter_context(rasterio.open(work/'ndvi.tif', 'w', **profile,
                                                        count=1, dtype='float32', nodata=np.nan))
            rgb_out = stack.enter_context(rasterio.open(work/'rgb.tif', 'w', **profile,
                                                       count=3, dtype='uint8', photometric='RGB'))
            source_out = stack.enter_context(rasterio.open(work/'source_index.tif', 'w', **profile,
                                                          count=1, dtype='uint16', nodata=0))
            for row in range(0, height, chunk_size):
                for col in range(0, width, chunk_size):
                    window = Window(col, row, min(chunk_size, width-col), min(chunk_size, height-row))
                    x, y = pixel_centers(transform, window)
                    roi = polygon_mask(*to_lonlat.transform(x, y), polygons) if polygons else np.ones(x.shape, bool)
                    aoi_count += int(roi.sum())
                    if mask_ds:
                        classes = sample_nearest(mask_ds, x, y, mask_transformer)
                        unknown_mask_count += int((roi & ~np.isfinite(classes)).sum())
                        roi &= classes == rice_class
                    roi_count += int(roi.sum())
                    merged = np.full(x.shape, np.nan, np.float32)
                    provenance = np.zeros(x.shape, np.uint16)
                    wl, wr = left+col*resolution, left+(col+window.width)*resolution
                    wt, wb = top-row*resolution, top-(row+window.height)*resolution
                    for index, (ds, projection, extent) in enumerate(zip(datasets, transformers, bounds), start=1):
                        if extent[2] <= wl or extent[0] >= wr or extent[3] <= wb or extent[1] >= wt:
                            continue
                        available = roi & (provenance == 0)
                        if not available.any():
                            break
                        values = sample_nearest(ds, x, y, projection)
                        take = available & np.isfinite(values) & (values >= -1) & (values <= 1)
                        merged[take], provenance[take] = values[take], index
                        counts[index-1] += int(take.sum())
                    finite = merged[np.isfinite(merged)]
                    valid_count += finite.size
                    total += float(finite.sum(dtype=np.float64))
                    if finite.size:
                        minimum, maximum = min(minimum, float(finite.min())), max(maximum, float(finite.max()))
                    ndvi_out.write(merged, 1, window=window)
                    rgb_out.write(ndvi_to_rgb(merged), window=window)
                    rgb_out.write_mask((provenance > 0).astype(np.uint8)*255, window=window)
                    source_out.write(provenance, 1, window=window)
                    peak = max(peak, psutil.Process().memory_info().rss)
        run = Path(tempfile.mkdtemp(dir=output, prefix=f'mosaic-{target_date}-'))
        for name in ('ndvi.tif', 'rgb.tif', 'source_index.tif'):
            os.replace(work/name, run/name)
        stats = dict(target_date=target_date, max_day_gap=max_day_gap, crs='EPSG:6933',
                     resolution_m=resolution, grid_pixels=width*height, aoi_pixels=aoi_count,
                     mask_unknown_pixels=unknown_mask_count,
                     mask_coverage_fraction=(aoi_count-unknown_mask_count)/aoi_count if aoi_count else None,
                     roi_pixels=roi_count,
                     valid_pixels=int(valid_count), roi_area_ha=roi_count*resolution**2/10000,
                     observed_area_ha=int(valid_count)*resolution**2/10000,
                     coverage_fraction=int(valid_count)/roi_count if roi_count else None,
                     mean_ndvi=total/int(valid_count) if valid_count else None,
                     min_ndvi=minimum if valid_count else None, max_ndvi=maximum if valid_count else None,
                     aoi=str(Path(aoi).resolve()) if aoi else None,
                     rice_mask=str(Path(rice_mask).resolve()) if rice_mask else None, rice_class=rice_class,
                     area_scope='Full AOI if supplied, otherwise source bounding union; pixel-center membership',
                     excluded_scenes=excluded, elapsed_seconds=time.perf_counter()-started,
                     sampled_peak_rss_mb=peak/1024**2,
                     ndvi=str((run/'ndvi.tif').resolve()), rgb=str((run/'rgb.tif').resolve()),
                     source_index=str((run/'source_index.tif').resolve()),
                     sources=[dict(index=i+1, scene_id=s[2], datetime=s[4], cloud_cover=s[1],
                                   ndvi=s[3], contributed_pixels=counts[i]) for i, s in enumerate(selected)])
        SentinelDownloader._write_json(output/'mosaic_summary.json', stats)
    return stats
