import rasterio
from rasterio.windows import Window
import numpy as np

class RasterWrapper:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.src = rasterio.open(file_path)

        self.meta = self.src.meta
        self.width = self.src.width
        self.height = self.src.height
        self.dtypes = self.src.dtypes
        self.crs = self.src.crs
        self.transform = self.src.transform
        self.count = self.src.count

    def read_band(self, band_index: int = 1) -> np.ndarray:
        #Index của band trong rasterio bắt đầu từ 1
        if band_index < 1 or band_index > self.count :
            raise ValueError(
                f"Error: Band_index {band_index} is not valid\n"
                f"File '{self.file_path}' has {self.count} band(s)."
            )
        return self.src.read(band_index)
    
    def get_metadata(self) -> dict:
        return {
            "width":     self.width,
            "height":    self.height,
            "count":     self.count,
            "dtype":     str(self.dtypes[0]),
            "crs":       self.crs,
            "transform": self.transform,
        }

    def close(self):
        if not self.src.closed:
            self.src.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _apply_transform(self, row: float, col: float) -> tuple:
        t = self.transform
        x = t.a * col + t.b * row + t.c
        y = t.d * col + t.e * row + t.f
        return x, y

    def get_pixel_size(self) -> tuple:
        return abs(self.transform.a), abs(self.transform.e)

    def get_bounds(self) -> dict:
        t = self.transform
        if abs(t.b) < 1e-9 and abs(t.d) < 1e-9:
            return {"left": t.c, 
                    "right": t.c + (self.width*t.a), 
                    "top": t.f, 
                    "bottom": t.f + (self.height*t.e)}
        corner = [self._apply_transform(0, 0),
                  self._apply_transform(0, self.width),
                  self._apply_transform(self.height, 0),
                  self._apply_transform(self.height, self.width)]
        x_coords = [c[0] for c in corner]
        y_coords = [c[1] for c in corner]
        bounds = {
            "left": min(x_coords),
            "right": max(x_coords),
            "top": max(y_coords),
            "bottom": min(y_coords)
        }
        return bounds
    def pixel_to_coords(self, row: int, col: int, offset: str = "center") -> tuple:
        col_offset = col + 0.5 if offset == "center" else col
        row_offset = row + 0.5 if offset == "center" else row
        return self._apply_transform(row_offset, col_offset)
    
    def read_chunk(self, band_index: int = 1, chunk_size: int = 256):
        for i in range(0, self.width, chunk_size):
            for j in range(0, self.height, chunk_size):
                actual_width = min(chunk_size, self.width - i)
                actual_height = min(chunk_size, self.height - j)
                w = Window(i, j, actual_width, actual_height)
                chunk = self.src.read(band_index, window=w)
                #chank.shape = (256, 256) nạp 256x256 pixel từ ảnh
                yield(chunk, w, i, j)


