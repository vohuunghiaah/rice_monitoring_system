import rasterio
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
            "dtype":     str(self.dtypes),
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

    def get_pixel_size(self) -> tuple:
        return abs(self.transform.a), abs(self.transform.e)
    
    def get_bounds()

