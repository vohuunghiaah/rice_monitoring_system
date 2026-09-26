"""Vectorized float32 NDVI kernel."""
import numpy as np


def calculate_ndvi(red, nir, valid=None):
    if red.shape != nir.shape:
        raise ValueError('RED and NIR shapes differ')
    red = np.asarray(red, dtype=np.float32)
    nir = np.asarray(nir, dtype=np.float32)
    denominator = nir + red
    mask = np.isfinite(red) & np.isfinite(nir) & (denominator != 0)
    if valid is not None:
        if valid.shape != red.shape:
            raise ValueError('Mask shape differs')
        mask &= valid
    result = np.full(red.shape, np.nan, dtype=np.float32)
    np.divide(nir - red, denominator, out=result, where=mask)
    result[(result < -1) | (result > 1) | ~np.isfinite(result)] = np.nan
    return result
