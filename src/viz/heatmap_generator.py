"""Greenness palette, not a crop diagnosis."""
import numpy as np


def ndvi_to_rgb(ndvi):
    anchors = [-1, 0, 0.3, 0.6, 1]
    colors = np.array([[30, 70, 150], [190, 50, 35], [245, 215, 70],
                       [100, 180, 65], [0, 90, 45]])
    values = np.nan_to_num(ndvi, nan=-1)
    rgb = np.stack([np.interp(values, anchors, colors[:, i])
                    for i in range(3)]).astype(np.uint8)
    rgb[:, ~np.isfinite(ndvi)] = 0
    return rgb
