from numpy._core.defchararray import index
import rasterio

class RasterWrapper:
    def __init__(self, file_path: str):
        self.src = rasterio.open(file_path)
        self.meta = self.src.meta

    def read_band(self, band_index: int):
        return self.src.read(band_index)
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.src.close()
        
        
