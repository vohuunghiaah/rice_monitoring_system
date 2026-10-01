"""Zero-copy CPU tensor adapter. This is the only NumPy-to-tensor boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

import torch

from src.raster_engine import PatchMetadata, RasterPair


@dataclass
class TensorPair:
    """Batch-one NCHW tensors sharing their owner arrays; metadata stays on CPU."""

    t1: torch.Tensor
    t2: torch.Tensor
    valid: torch.Tensor
    metadata: PatchMetadata


def tensor_pairs(pairs: Iterable[RasterPair]) -> Iterator[TensorPair]:
    """Adapt without stack/cast/contiguous copies or an unbounded prefetch queue.

    from_numpy retains storage ownership. Device transfer, pinning and batching
    may allocate; zero-copy is promised only for this CPU adapter.
    """
    for pair in pairs:
        pair.validate()
        yield TensorPair(torch.from_numpy(pair.t1).unsqueeze(0),
                         torch.from_numpy(pair.t2).unsqueeze(0),
                         torch.from_numpy(pair.valid)[None, None], pair.metadata)
