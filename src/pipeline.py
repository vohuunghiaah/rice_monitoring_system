"""Local windowed processing; NumPy implements SCL nearest-neighbor sampling."""
from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
import time

import numpy as np
import psutil
import rasterio
from rasterio.windows import Window

from src.core.ndvi_engine import calculate_ndvi
from src.io.downloader import SentinelDownloader
from src.io.raster_wrapper import RasterWrapper
from src.viz.heatmap_generator import ndvi_to_rgb


def read_scl(scl, target, window):
    """Map target pixel centers into SCL grid, reading only the needed window."""
    if scl.crs != target.crs:
        raise ValueError('SCL and spectral bands must use the same CRS')
    transform = ~scl.transform * target.transform
    rows, cols = np.meshgrid(
        np.arange(window.row_off, window.row_off + window.height) + .5,
        np.arange(window.col_off, window.col_off + window.width) + .5, indexing='ij')
    sc = np.floor(transform.a * cols + transform.b * rows + transform.c).astype(int)
    sr = np.floor(transform.d * cols + transform.e * rows + transform.f).astype(int)
    inside = (sr >= 0) & (sr < scl.height) & (sc >= 0) & (sc < scl.width)
    result = np.zeros(sr.shape, dtype=np.uint8)
    if np.any(inside):
        r0, r1 = int(sr[inside].min()), int(sr[inside].max()) + 1
        c0, c1 = int(sc[inside].min()), int(sc[inside].max()) + 1
        data = scl.read(1, window=Window(c0, r0, c1-c0, r1-r0), masked=True).filled(0)
        result[inside] = data[sr[inside]-r0, sc[inside]-c0]
    return result


def process_scene(bands, output_dir, scene_id='local', chunk_size=512, calibration=None,
                  scene_metadata=None):
    if not isinstance(chunk_size, int) or not 1 <= chunk_size <= 2048:
        raise ValueError('chunk_size must be an integer in [1, 2048]')
    if Path(scene_id).name != scene_id or scene_id in ('', '.', '..'):
        raise ValueError('Invalid scene_id')
    calibration = calibration or {}
    scene_metadata = scene_metadata or {}
    effective_calibration = {}
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    count, total, minimum, maximum = 0, 0.0, float('inf'), float('-inf')
    # A new run directory keeps prior complete outputs intact on failure.
    with tempfile.TemporaryDirectory(dir=output, prefix='.processing-') as temp:
        temp = Path(temp)
        with rasterio.Env(GDAL_CACHEMAX=32 * 1024 * 1024, GDAL_TIFF_INTERNAL_MASK=True), ExitStack() as stack:
            red = stack.enter_context(RasterWrapper(bands['B04']))
            nir = stack.enter_context(rasterio.open(bands['B08']))
            scl = stack.enter_context(rasterio.open(bands['SCL']))
            if red.crs is None or any(ds.count != 1 for ds in (red.src, nir, scl)):
                raise ValueError('Expected georeferenced single-band inputs')
            if (red.width, red.height, red.crs, red.transform) != (
                    nir.width, nir.height, nir.crs, nir.transform):
                raise ValueError('RED/NIR grids differ; coregister inputs first')
            if scl.crs != red.crs:
                raise ValueError('SCL CRS differs; coregister inputs first')
            # Restrict SCL sampling to aligned equal/coarser grids to bound reads.
            mapping = ~scl.transform * red.transform
            if (abs(mapping.b) > 1e-8 or abs(mapping.d) > 1e-8
                    or not 0 < mapping.a <= 1 or not 0 < mapping.e <= 1):
                raise ValueError('SCL must be aligned and equal/coarser resolution')
            profile = dict(driver='GTiff', width=red.width, height=red.height,
                           crs=red.crs, transform=red.transform, tiled=True,
                           blockxsize=256, blockysize=256, compress='deflate', BIGTIFF='IF_SAFER')
            ndvi_dst = stack.enter_context(rasterio.open(temp/'ndvi.tif', 'w',
                **profile, count=1, dtype='float32', nodata=np.nan))
            rgb_dst = stack.enter_context(rasterio.open(temp/'rgb.tif', 'w',
                **profile, count=3, dtype='uint8', photometric='RGB'))
            for raw_red, window, _, _ in red.read_chunk(chunk_size=chunk_size):
                raw_nir = nir.read(1, window=window)
                valid = (red.src.read_masks(1, window=window) > 0) & (nir.read_masks(1, window=window) > 0)
                # SCL 4 vegetation, 5 bare soil, 6 water, 7 unclassified.
                valid &= np.isin(read_scl(scl, red, window), [4, 5, 6, 7])
                values = []
                for key, raw, ds in [('B04', raw_red, red.src), ('B08', raw_nir, nir)]:
                    params = calibration.get(key, {})
                    scale = params.get('scale', ds.scales[0])
                    offset = params.get('offset', ds.offsets[0])
                    if not np.isfinite(scale) or not np.isfinite(offset) or scale <= 0:
                        raise ValueError('Invalid reflectance scale/offset')
                    effective_calibration[key] = dict(scale=float(scale), offset=float(offset))
                    values.append(raw.astype(np.float32) * np.float32(scale) + np.float32(offset))
                ndvi = calculate_ndvi(*values, valid=valid)
                ndvi_dst.write(ndvi, 1, window=window)
                rgb_dst.write(ndvi_to_rgb(ndvi), window=window)
                rgb_dst.write_mask(np.isfinite(ndvi).astype(np.uint8) * 255, window=window)
                finite = ndvi[np.isfinite(ndvi)]
                if finite.size:
                    count += int(finite.size)
                    total += float(finite.sum(dtype=np.float64))
                    minimum = min(minimum, float(finite.min()))
                    maximum = max(maximum, float(finite.max()))
                peak_rss = max(peak_rss, process.memory_info().rss)
            pixels = red.width * red.height
        # Publish both rasters together under a unique run directory. Summary is
        # the completion marker and is replaced atomically only after both exist.
        run = Path(tempfile.mkdtemp(dir=output, prefix=f'{scene_id}-'))
        for name in ('ndvi.tif', 'rgb.tif'):
            os.replace(temp/name, run/name)
        stats = dict(scene_id=scene_id, datetime=scene_metadata.get('datetime'),
                     cloud_cover=scene_metadata.get('cloud_cover'), valid_pixels=count, total_pixels=pixels,
                     valid_fraction=count/pixels, mean_ndvi=total/count if count else None,
                     min_ndvi=minimum if count else None, max_ndvi=maximum if count else None,
                     elapsed_seconds=time.perf_counter()-start,
                     sampled_peak_rss_mb=peak_rss/1024**2,
                     ndvi=str((run/'ndvi.tif').resolve()), rgb=str((run/'rgb.tif').resolve()),
                     input_bands={k: str(Path(v).resolve()) for k, v in bands.items()},
                     calibration=effective_calibration, chunk_size=chunk_size)
        SentinelDownloader._write_json(output/f'{scene_id}_summary.json', stats)
    return stats
