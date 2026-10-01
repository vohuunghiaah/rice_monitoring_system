"""Module 1: bounded NumPy preprocessing; rasterio is used only for raster I/O."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from numbers import Real
from typing import Iterator

import numpy as np
import rasterio
from affine import Affine
from rasterio.windows import Window


@dataclass(frozen=True)
class Band:
    """A single-band input with explicit calibration (never guessed from DN)."""

    name: str
    path: Path
    scale: float = 1.0
    offset: float = 0.0


@dataclass(frozen=True)
class Scene:
    """Ordered bands and optional aligned binary quality mask: 1 means clear."""

    scene_id: str
    bands: tuple[Band, ...]
    quality: Path | None = None


@dataclass(frozen=True)
class Grid:
    """Reference pixel grid; CRS is serialized as WKT across module boundaries."""

    width: int
    height: int
    transform: Affine
    crs_wkt: str


@dataclass(frozen=True)
class PatchMetadata:
    """Destination core and its offset inside the padded CHW input patch."""

    grid: Grid
    window: Window
    sub_affine: Affine
    core_affine: Affine
    halo: int
    scene_ids: tuple[str, str]
    channels: tuple[str, ...]


@dataclass
class RasterPair:
    """Owned float32 CHW arrays; validity is joint across dates and channels.

    Arrays are not recycled after yield, so asynchronous consumers remain safe.
    Consumers must bound their queues and must not mutate shared arrays.
    """

    t1: np.ndarray
    t2: np.ndarray
    valid: np.ndarray
    metadata: PatchMetadata

    def validate(self) -> None:
        """Reject incompatible buffers before sharing storage with an inference backend."""
        if (self.t1.ndim != 3 or self.t1.shape != self.t2.shape
                or self.valid.shape != self.t1.shape[1:]
                or self.t1.dtype != np.float32 or self.t2.dtype != np.float32
                or self.valid.dtype != np.bool_):
            raise ValueError('Expected matching float32 CHW images and boolean HW validity')
        if any(not a.flags.c_contiguous or not a.flags.writeable
               for a in (self.t1, self.t2, self.valid)):
            raise ValueError('Shared buffers must be writable and C-contiguous')


def translated(transform: Affine, col: int | float, row: int | float) -> Affine:
    """Translate in pixel space without version-dependent Affine operators."""
    a, b, c, d, e, f = transform[:6]
    return Affine(a, b, c+a*col+b*row, d, e, f+d*col+e*row)


def erode_clear(clear: np.ndarray, radius: int) -> np.ndarray:
    """Square-window erosion via NumPy integral sums; outside is unknown."""
    if type(radius) is not int or radius < 0 or clear.ndim != 2 or clear.dtype != np.bool_:
        raise ValueError('Expected boolean HW clear mask and nonnegative integer radius')
    if radius == 0:
        return clear.copy()
    padded = np.pad(clear, radius, constant_values=False)
    integral = np.pad(padded, ((1, 0), (1, 0))).cumsum(0, dtype=np.int64).cumsum(1)
    width = 2*radius+1
    counts = integral[width:, width:] - integral[:-width, width:]
    counts -= integral[width:, :-width]
    counts += integral[:-width, :-width]
    return counts == width*width


def normalized_difference(a: np.ndarray, b: np.ndarray, out: np.ndarray,
                          scratch: np.ndarray, epsilon: float = 1e-6) -> np.ndarray:
    """Compute (a-b)/(a+b) into disjoint float32 buffers; invalid ratios are NaN."""
    arrays = (a, b, out, scratch)
    if any(x.shape != a.shape or x.dtype != np.float32 for x in arrays):
        raise ValueError('Expected equally shaped float32 arrays')
    if epsilon <= 0 or not np.isfinite(epsilon):
        raise ValueError('epsilon must be finite and positive')
    if any(np.shares_memory(x, y) for x, y in
           ((out, a), (out, b), (scratch, a), (scratch, b), (out, scratch))):
        raise ValueError('Output and scratch must not alias inputs or each other')
    with np.errstate(over='ignore', invalid='ignore'):
        np.add(a, b, out=scratch)
        np.subtract(a, b, out=out)
    valid = np.isfinite(out) & np.isfinite(scratch) & (np.abs(scratch) > epsilon)
    with np.errstate(over='ignore', invalid='ignore'):
        np.divide(out, scratch, out=out, where=valid)
    out[~valid | ~np.isfinite(out)] = np.nan
    return out


class RasterEngine:
    """Stream registered temporal inputs with halo, fixed shape and bounded RAM.

    No implicit reprojection or resampling is performed. Register all bands and
    quality masks upstream; grid equality is checked before the first yield.
    """

    def __init__(self, t1: Scene, t2: Scene, core_size: int = 256, halo: int = 32,
                 ndvi: tuple[str, str] | None = ('B08', 'B04'),
                 quality_radius: int = 0) -> None:
        if (type(core_size) is not int or type(halo) is not int
                or core_size <= 0 or halo < 0):
            raise ValueError('core_size must be positive and halo nonnegative integers')
        names = tuple(b.name for b in t1.bands)
        if (not names or any(not isinstance(n, str) or not n.strip() for n in names)
                or len(set(names)) != len(names) or names != tuple(b.name for b in t2.bands)):
            raise ValueError('Both dates need the same unique ordered channel names')
        if ndvi is not None and (not isinstance(ndvi, tuple) or len(ndvi) != 2
                                or ndvi[0] == ndvi[1] or any(n not in names for n in ndvi)
                                or 'NDVI' in names):
            raise ValueError('NDVI needs named input bands and a free NDVI channel name')
        for band in (*t1.bands, *t2.bands):
            if (any(not isinstance(v, Real) or isinstance(v, bool) for v in (band.scale, band.offset))
                    or not np.isfinite([band.scale, band.offset]).all() or band.scale <= 0
                    or band.scale > float(np.finfo(np.float32).max)
                    or band.scale < float(np.nextafter(np.float32(0), np.float32(1)))
                    or abs(band.offset) > float(np.finfo(np.float32).max)):
                raise ValueError('Calibration must be finite, with positive scale')
        self.scenes, self.core_size, self.halo, self.ndvi = (t1, t2), core_size, halo, ndvi
        if type(quality_radius) is not int or quality_radius < 0:
            raise ValueError('quality_radius must be a nonnegative integer')
        if quality_radius and any(s.quality is None for s in self.scenes):
            raise ValueError('quality_radius requires clear masks at both dates')
        if any(not isinstance(s.scene_id, str) or not s.scene_id.strip() for s in self.scenes):
            raise ValueError('scene_id must be a nonempty string')
        self.quality_radius = quality_radius
        self.channels = names + (('NDVI',) if ndvi else ())

    def __iter__(self) -> Iterator[RasterPair]:
        """Open independent handles per iteration; release them on close/exhaustion."""
        # Do not suspend a thread-local GDAL Env across yields: independent
        # iterators may be interleaved or closed in a different order.
        with ExitStack() as stack:
            sources = [[stack.enter_context(rasterio.open(b.path)) for b in s.bands]
                       for s in self.scenes]
            qualities = [stack.enter_context(rasterio.open(s.quality)) if s.quality else None
                         for s in self.scenes]
            ref = sources[0][0]
            if (ref.crs is None or not np.isfinite(ref.transform[:6]).all()
                    or not np.isfinite(ref.transform.determinant) or ref.transform.determinant == 0):
                raise ValueError('Inputs require a CRS and invertible affine')
            grid = Grid(ref.width, ref.height, ref.transform, ref.crs.to_wkt())
            for ds in [*sources[0], *sources[1], *(q for q in qualities if q is not None)]:
                if (ds.count != 1 or (ds.width, ds.height, ds.crs, ds.transform) !=
                        (ref.width, ref.height, ref.crs, ref.transform)):
                    raise ValueError('Input grids differ; coregister all bands and quality masks first')
            size, h = self.core_size, self.halo
            extent = size + 2*h
            for row in range(0, grid.height, size):
                for col in range(0, grid.width, size):
                    core = Window(col, row, min(size, grid.width-col), min(size, grid.height-row))
                    x0, y0 = max(0, col-h), max(0, row-h)
                    x1, y1 = min(grid.width, col+size+h), min(grid.height, row+size+h)
                    read_window = Window(x0, y0, x1-x0, y1-y0)
                    region = (slice(y0-row+h, y1-row+h), slice(x0-col+h, x1-col+h))
                    images, masks = [], []
                    for scene, datasets, quality in zip(self.scenes, sources, qualities):
                        image = np.zeros((len(self.channels), extent, extent), np.float32)
                        valid = np.zeros((extent, extent), bool)
                        valid[region] = True
                        for i, (band, ds) in enumerate(zip(scene.bands, datasets)):
                            # Window-sized scratch accommodates GDAL layouts without scene-sized buffers.
                            raw = ds.read(1, window=read_window, out_dtype='float32')
                            with np.errstate(over='ignore', invalid='ignore'):
                                np.multiply(raw, np.float32(band.scale), out=raw)
                                np.add(raw, np.float32(band.offset), out=raw)
                            image[i][region] = raw
                            valid[region] &= (ds.read_masks(1, window=read_window) > 0) & np.isfinite(raw)
                        if quality is not None:
                            radius = self.quality_radius
                            qx0, qy0 = max(0, x0-radius), max(0, y0-radius)
                            qx1, qy1 = min(grid.width, x1+radius), min(grid.height, y1+radius)
                            qw = Window(qx0, qy0, qx1-qx0, qy1-qy0)
                            q = quality.read(1, window=qw)
                            observed = quality.read_masks(1, window=qw) > 0
                            if np.any(observed & ~np.isin(q, (0, 1))):
                                raise ValueError('Quality must be binary 0/1, not raw SCL')
                            clear = erode_clear((q == 1) & observed, radius)
                            valid[region] &= clear[y0-qy0:y1-qy0, x0-qx0:x1-qx0]
                        if self.ndvi:
                            a, b = (self.channels.index(n) for n in self.ndvi)
                            normalized_difference(image[a], image[b], image[-1], np.empty_like(valid, dtype=np.float32))
                            valid &= np.isfinite(image[-1])
                        image[:, ~valid] = 0
                        images.append(image)
                        masks.append(valid)
                    joint = masks[0] & masks[1]
                    for image in images:
                        image[:, ~joint] = 0
                    metadata = PatchMetadata(grid, core,
                        translated(grid.transform, col-h, row-h),
                        translated(grid.transform, col, row), h,
                        tuple(s.scene_id for s in self.scenes), self.channels)
                    yield RasterPair(images[0], images[1], joint, metadata)
