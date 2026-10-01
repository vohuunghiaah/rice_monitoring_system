"""Bounded-memory, globally accumulated metrics on valid change pixels."""
from __future__ import annotations

import numpy as np


class ChangeMetrics:
    """Exact threshold IoU and histogram approximation to average precision.

    AP integrates a stepwise precision-recall curve, not trapezoidal PR AUC.
    Quantized scores in each bin are ties. Increase bins to reduce this error.
    """

    def __init__(self, threshold: float = .5, bins: int = 4096) -> None:
        if not np.isfinite(threshold) or not 0 <= threshold <= 1 or type(bins) is not int or bins < 2:
            raise ValueError('Invalid threshold or histogram size')
        self.threshold = threshold
        self.positive = np.zeros(bins, np.int64)
        self.negative = np.zeros(bins, np.int64)
        self.tp = self.fp = self.fn = self.valid_count = 0

    def update(self, probability: np.ndarray, target: np.ndarray, valid: np.ndarray) -> None:
        """Accumulate each reconstructed core once; reject invalid labelled values."""
        if (probability.shape != target.shape or probability.shape != valid.shape
                or valid.dtype != np.bool_):
            raise ValueError('Metric shapes differ')
        p, y = probability[valid], target[valid]
        if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)) or np.any((y != 0) & (y != 1)):
            raise ValueError('Expected probabilities [0,1] and binary labels')
        y = y.astype(bool)
        pred = p >= self.threshold
        self.tp += int(np.count_nonzero(pred & y))
        self.fp += int(np.count_nonzero(pred & ~y))
        self.fn += int(np.count_nonzero(~pred & y))
        self.valid_count += p.size
        index = np.minimum((p*(len(self.positive)-1)).astype(np.int64), len(self.positive)-1)
        self.positive += np.bincount(index[y], minlength=len(self.positive))
        self.negative += np.bincount(index[~y], minlength=len(self.negative))

    def compute(self) -> dict[str, float | int | None]:
        """Return undefined IoU/AP as None rather than an inflated perfect score."""
        positives = int(self.positive.sum())
        tp = np.cumsum(self.positive[::-1], dtype=np.float64)
        fp = np.cumsum(self.negative[::-1], dtype=np.float64)
        precision = np.divide(tp, tp+fp, out=np.zeros_like(tp), where=tp+fp > 0)
        ap = float(np.sum(precision*self.positive[::-1])/positives) if positives else None
        union = self.tp+self.fp+self.fn
        return dict(change_iou=self.tp/union if union else None,
                    pr_auc_ap_histogram=ap, valid_pixels=self.valid_count,
                    precision=self.tp/(self.tp+self.fp) if self.tp+self.fp else None,
                    recall=self.tp/positives if positives else None,
                    threshold=self.threshold, histogram_bins=len(self.positive),
                    positive_pixels=positives, tp=self.tp, fp=self.fp, fn=self.fn)
