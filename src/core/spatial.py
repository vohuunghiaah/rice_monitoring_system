"""NumPy sampling and point-in-polygon; PROJ only converts coordinates."""
import json
from pathlib import Path

import numpy as np
from rasterio.windows import Window


def pixel_centers(transform, window):
    rows, cols = np.meshgrid(
        np.arange(window.row_off, window.row_off + window.height) + .5,
        np.arange(window.col_off, window.col_off + window.width) + .5, indexing='ij')
    return (transform.a * cols + transform.b * rows + transform.c,
            transform.d * cols + transform.e * rows + transform.f)


def sample_nearest(dataset, x, y, transformer, max_read_pixels=4_194_304):
    """Inverse-map destination centers; never ask GDAL to resample/reproject.

    A large projected window is split into source blocks. This avoids an
    unbounded source rectangle when resolution or projection changes sharply.
    """
    sx, sy = transformer.transform(x, y)
    inv = ~dataset.transform
    cols = np.floor(inv.a * sx + inv.b * sy + inv.c)
    rows = np.floor(inv.d * sx + inv.e * sy + inv.f)
    inside = (np.isfinite(rows) & np.isfinite(cols) & (rows >= 0)
              & (rows < dataset.height) & (cols >= 0) & (cols < dataset.width))
    result = np.full(x.shape, np.nan, dtype=np.float32)
    if not inside.any():
        return result
    rr, cc = rows[inside].astype(np.int64), cols[inside].astype(np.int64)
    r0, r1, c0, c1 = rr.min(), rr.max()+1, cc.min(), cc.max()+1
    if (r1-r0)*(c1-c0) <= max_read_pixels:
        data = dataset.read(1, window=Window(int(c0), int(r0), int(c1-c0), int(r1-r0)),
                            out_dtype='float32', masked=True).filled(np.nan)
        result[inside] = data[rr-r0, cc-c0]
    else:
        # Group requested indices by fixed source block; each read <= 256^2.
        blocks_per_row = (dataset.width + 255)//256
        block_ids = (rr//256)*blocks_per_row + cc//256
        order = np.argsort(block_ids, kind='stable')
        boundaries = np.r_[0, np.flatnonzero(np.diff(block_ids[order]))+1, len(order)]
        positions = np.flatnonzero(inside)
        for lo, hi in zip(boundaries[:-1], boundaries[1:]):
            selected = order[lo:hi]
            br, bc = rr[selected[0]]//256*256, cc[selected[0]]//256*256
            window = Window(int(bc), int(br), min(256, dataset.width-int(bc)),
                            min(256, dataset.height-int(br)))
            data = dataset.read(1, window=window, out_dtype='float32', masked=True).filled(np.nan)
            result.flat[positions[selected]] = data[rr[selected]-br, cc[selected]-bc]
    return result


def load_polygons(path):
    """Read RFC 7946 Polygon/MultiPolygon in lon/lat; reject dateline AOIs."""
    document = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if 'crs' in document:
        raise ValueError('AOI must be RFC 7946 WGS84 GeoJSON without a crs member')
    features = document.get('features', [document])
    polygons = []
    for feature in features:
        geometry = feature.get('geometry', feature)
        if geometry is None:
            raise ValueError('Empty AOI geometry')
        kind = geometry.get('type')
        if kind not in ('Polygon', 'MultiPolygon'):
            raise ValueError('AOI supports Polygon/MultiPolygon only')
        coords = geometry['coordinates']
        for polygon in ([coords] if kind == 'Polygon' else coords):
            rings = []
            for ring in polygon:
                arr = np.asarray(ring, dtype=float)
                if (arr.ndim != 2 or arr.shape[0] < 4 or arr.shape[1] != 2
                        or not np.isfinite(arr).all() or not np.array_equal(arr[0], arr[-1])
                        or np.any(np.abs(arr[:, 0]) > 180) or np.any(np.abs(arr[:, 1]) > 85)
                        or np.ptp(arr[:, 0]) > 180):
                    raise ValueError('Invalid/unsupported ring: closed lon/lat, latitude within +/-85, no dateline')
                rings.append(arr)
            if not rings:
                raise ValueError('Empty polygon')
            polygons.append(rings)
    if not polygons:
        raise ValueError('Empty AOI')
    return polygons


def _in_ring(x, y, ring):
    # Even-odd ray casting: loop over edges, vectorize over all pixel centers.
    # Half-open edge convention avoids counting a shared vertex twice.
    inside = np.zeros(x.shape, dtype=bool)
    for (x1, y1), (x2, y2) in zip(ring[:-1], ring[1:]):
        if y1 != y2:
            crosses = (y1 > y) != (y2 > y)
            inside ^= crosses & (x < (x2-x1)*(y-y1)/(y2-y1)+x1)
    return inside


def polygon_mask(lon, lat, polygons):
    result = np.zeros(lon.shape, dtype=bool)
    for rings in polygons:
        part = _in_ring(lon, lat, rings[0])
        for hole in rings[1:]:
            part &= ~_in_ring(lon, lat, hole)
        result |= part
    return result
