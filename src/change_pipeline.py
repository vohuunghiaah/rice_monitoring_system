"""Application orchestration: connect preprocessing, inference and raster output."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING, Iterator, Protocol

import numpy as np
import rasterio

from src.raster_engine import RasterEngine, RasterPair, translated

if TYPE_CHECKING:
    from torch import nn


def same_path(a: Path, b: Path) -> bool:
    """Compare resolved paths and existing hard links without opening their contents."""
    return a.resolve() == b.resolve() or (a.exists() and b.exists() and a.samefile(b))


@contextmanager
def output_lock(destination: Path) -> Iterator[None]:
    """Fail fast if another cooperating writer owns this destination.

    A crashed process may leave a lock; inspect its PID before manual removal.
    """
    lock = destination.with_name(destination.name+'.lock')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError(f'Output is locked: {lock}') from exc
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


class Predictor(Protocol):
    """Inference port accepts a pair and returns a full HW probability patch."""

    def __call__(self, pair: RasterPair) -> np.ndarray:
        ...


class TorchPredictor:
    """Synchronous batch-one inference adapter; GPU transfer is explicit."""

    def __init__(self, model: nn.Module, device: str = 'cpu') -> None:
        import torch
        self.device = torch.device(device)
        self.model = model.to(self.device).eval()

    def __call__(self, pair: RasterPair) -> np.ndarray:
        import torch
        from src.dataset_bridge import tensor_pairs
        tensor = next(tensor_pairs((pair,)))
        with torch.inference_mode():
            logits = self.model(tensor.t1.to(self.device), tensor.t2.to(self.device))
            if logits.shape != tensor.valid.shape or not torch.isfinite(logits).all():
                raise ValueError('Model must return finite N1HW logits at input resolution')
            return torch.sigmoid(logits.float())[0, 0].cpu().numpy()


def predict_raster(engine: RasterEngine, predictor: Predictor, destination: Path,
                   threshold: float = .5, provenance: dict[str, str] | None = None) -> Path:
    """Write disjoint halo-cropped cores, then atomically publish one GeoTIFF.

    Class 0 = unchanged, 1 = changed, 255 = unknown. Output includes its grid,
    channel order and scene IDs. Probability blending is deliberately avoided.
    Consumers see the prior complete file or the new complete file on failure.
    """
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('threshold must be in [0,1]')
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite a source, even if the caller passes an equivalent path.
    inputs = [b.path for s in engine.scenes for b in s.bands]
    inputs += [s.quality for s in engine.scenes if s.quality is not None]
    if any(same_path(destination, Path(p)) for p in inputs):
        raise ValueError('Output must not overwrite an input')
    with output_lock(destination), rasterio.Env(GDAL_CACHEMAX=32*1024*1024), tempfile.TemporaryDirectory(
            prefix='.change-', dir=destination.parent) as tmp:
        if any(Path(str(destination)+suffix).exists() for suffix in ('.msk', '.aux.xml', '.ovr')):
            raise ValueError('Output has external sidecars; choose a new destination')
        staged = Path(tmp)/'mask.tif'
        iterator = iter(engine)
        try:
            first = next(iterator)
            grid = first.metadata.grid
            with rasterio.open(
                    staged, 'w', driver='GTiff', width=grid.width, height=grid.height,
                    count=1, dtype='uint8', crs=grid.crs_wkt, transform=grid.transform,
                    nodata=255, tiled=True, blockxsize=256, blockysize=256,
                    compress='deflate', BIGTIFF='IF_SAFER') as dst:
                dst.update_tags(scene_ids=json.dumps(first.metadata.scene_ids),
                                channels=json.dumps(first.metadata.channels),
                                threshold=str(threshold), stitching='halo_core_crop',
                                quality_radius=str(engine.quality_radius),
                                provenance=json.dumps(provenance or {}, sort_keys=True))
                expected = iter((row, col) for row in range(0, grid.height, engine.core_size)
                                for col in range(0, grid.width, engine.core_size))
                import itertools
                for pair in itertools.chain((first,), iterator):
                    meta = pair.metadata
                    pair.validate()
                    location = next(expected, None)
                    row, col = meta.window.row_off, meta.window.col_off
                    if (location != (row, col) or meta.grid != grid
                            or meta.halo != engine.halo or meta.channels != engine.channels
                            or meta.scene_ids != tuple(s.scene_id for s in engine.scenes)
                            or meta.window.height != min(engine.core_size, grid.height-row)
                            or meta.window.width != min(engine.core_size, grid.width-col)
                            or pair.t1.shape != (len(engine.channels),
                                engine.core_size+2*engine.halo, engine.core_size+2*engine.halo)
                            or meta.core_affine != translated(grid.transform, col, row)
                            or meta.sub_affine != translated(grid.transform, col-meta.halo, row-meta.halo)):
                        raise ValueError('Inconsistent reconstruction metadata')
                    h = meta.halo
                    rows, cols = int(meta.window.height), int(meta.window.width)
                    crop = (slice(h, h+rows), slice(h, h+cols))
                    valid = pair.valid[crop]
                    mask = np.full((rows, cols), 255, np.uint8)
                    if valid.any():
                        probability = np.asarray(predictor(pair))
                        if probability.shape != pair.valid.shape:
                            raise ValueError('Predictor must return full HW patch')
                        p = probability[crop]
                        if not np.isfinite(p[valid]).all() or np.any((p[valid] < 0) | (p[valid] > 1)):
                            raise ValueError('Predictor returned invalid probabilities')
                        mask[valid] = (p[valid] >= threshold).astype(np.uint8)
                    dst.write(mask, 1, window=meta.window)
                if next(expected, None) is not None:
                    raise ValueError('Incomplete patch stream; refusing to publish missing pixels')
        finally:
            iterator.close()
        os.replace(staged, destination)
    return destination
