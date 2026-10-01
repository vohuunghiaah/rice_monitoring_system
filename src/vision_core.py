"""Module 2: shared Siamese encoder, segmentation logits and masked losses.

No raster handles, CRS operations or rasterio dependency belong in this module.
"""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F


def _block(inputs: int, outputs: int) -> nn.Sequential:
    """Local convolution block; no patch-dependent spatial normalization."""
    return nn.Sequential(nn.Conv2d(inputs, outputs, 3, padding=1), nn.ReLU(),
                         nn.Conv2d(outputs, outputs, 3, padding=1), nn.ReLU())


class SiameseUNet(nn.Module):
    """FC-Siam-diff variant with shared weights and absolute feature differences.

    Outputs raw binary change logits at input resolution. Inputs must share
    NCHW shape, with spatial dimensions divisible by four. This binary head
    segments change; it does not independently classify rice land cover.
    """

    def __init__(self, channels: int, width: int = 32) -> None:
        super().__init__()
        if type(channels) is not int or type(width) is not int or channels <= 0 or width <= 0:
            raise ValueError('channels and width must be positive')
        self.channels = channels
        self.encoder = nn.ModuleList([_block(channels, width), _block(width, 2*width),
                                      _block(2*width, 4*width)])
        self.decode1 = _block(6*width, 2*width)
        self.decode0 = _block(3*width, width)
        self.head = nn.Conv2d(width, 1, 1)

    def _encode(self, image: torch.Tensor) -> list[torch.Tensor]:
        features = []
        for i, block in enumerate(self.encoder):
            image = block(F.max_pool2d(image, 2) if i else image)
            features.append(image)
        return features

    def forward(self, t1: torch.Tensor, t2: torch.Tensor) -> torch.Tensor:
        """Return logits; absolute differences make temporal swapping invariant."""
        if (t1.shape != t2.shape or t1.ndim != 4 or t1.shape[0] < 1
                or t1.shape[1] != self.channels or any(s < 4 or s % 4 for s in t1.shape[-2:])
                or not t1.is_floating_point() or t1.dtype != t2.dtype or t1.device != t2.device):
            raise ValueError('Expected equal NCHW shapes with H/W divisible by four')
        diff = [torch.abs(a-b) for a, b in zip(self._encode(t1), self._encode(t2))]
        x = self.decode1(torch.cat((F.interpolate(diff[2], scale_factor=2, mode='nearest'), diff[1]), 1))
        x = self.decode0(torch.cat((F.interpolate(x, scale_factor=2, mode='nearest'), diff[0]), 1))
        return self.head(x)


class FocalTverskyLoss(nn.Module):
    """Masked focal BCE plus soft Tversky, reduced over valid pixels only.

    beta weights false negatives; alpha weights false positives. All-invalid
    batches return differentiable zero. Targets on valid pixels must be 0/1.
    Use a core-only validity mask in training to avoid weighting halos twice.
    """

    def __init__(self, positive_weight: float = .75, gamma: float = 2.,
                 alpha: float = .3, beta: float = .7, focal_fraction: float = .5) -> None:
        super().__init__()
        if not (all(math.isfinite(v) for v in (positive_weight, gamma, alpha, beta, focal_fraction))
                and 0 < positive_weight < 1 and gamma >= 0 and alpha > 0 and beta > 0
                and 0 <= focal_fraction <= 1):
            raise ValueError('Invalid loss parameters')
        self.positive_weight, self.gamma = positive_weight, gamma
        self.alpha, self.beta, self.focal_fraction = alpha, beta, focal_fraction

    def forward(self, logits: torch.Tensor, target: torch.Tensor,
                valid: torch.Tensor) -> torch.Tensor:
        """Compute stable float32 BCE directly from logits, including under AMP."""
        if (logits.shape != target.shape or logits.shape != valid.shape
                or logits.ndim != 4 or logits.shape[1] != 1 or valid.dtype != torch.bool
                or not logits.is_floating_point() or logits.device != target.device
                or logits.device != valid.device):
            raise ValueError('logits, target and valid must share N1HW shape')
        z = logits.float()[valid.bool()]
        y = target.float()[valid.bool()]
        if z.numel() == 0:
            return z.sum()
        if not torch.isfinite(z).all() or not ((y == 0) | (y == 1)).all():
            raise ValueError('Valid logits must be finite and targets binary')
        bce = F.binary_cross_entropy_with_logits(z, y, reduction='none')
        pt = torch.exp(-bce)
        weight = y*self.positive_weight + (1-y)*(1-self.positive_weight)
        focal = (weight*(1-pt).pow(self.gamma)*bce).mean()
        p = torch.sigmoid(z)
        tp = (p*y).sum()
        fp = (p*(1-y)).sum()
        fn = ((1-p)*y).sum()
        tversky = 1-(tp+1e-6)/(tp+self.alpha*fp+self.beta*fn+1e-6)
        return self.focal_fraction*focal + (1-self.focal_fraction)*tversky
