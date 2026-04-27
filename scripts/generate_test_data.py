"""
generate_test_data.py
=====================
Script tạo DỮ LIỆU TEST GIẢ LẬP Sentinel-2 (Band 4 và Band 8).

Mục đích: Bạn chưa có ảnh vệ tinh thật, nhưng cần dữ liệu đúng định dạng
để test class RasterWrapper đang viết ở Task 1.1.

File này tạo ra 2 file GeoTIFF nhỏ (512x512 pixel) trong data/01_raw/:
  - B04_RED_test.tif   ← Band 4 (Red light)
  - B08_NIR_test.tif   ← Band 8 (Near-Infrared)

Giá trị pixel được mô phỏng theo 3 vùng thực địa ĐBSCL:
  - Vùng lúa khỏe mạnh : NIR cao (~3500), RED thấp (~800)  → NDVI ≈ +0.63
  - Vùng xâm nhập mặn  : NIR thấp (~1000), RED cao (~1200) → NDVI ≈ -0.09
  - Vùng mặt nước/sông : NIR rất thấp (~200), RED thấp (~300) → NDVI ≈ -0.20

Cách chạy:
  cd rice_monitoring_system
  python scripts/generate_test_data.py
"""

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
import os


def create_sentinel2_like_bands():
    # --- CẤU HÌNH KÍCH THƯỚC ẢNH TEST ---
    # Dùng 512x512 thay vì 10980x10980 thật để test nhanh
    WIDTH = 512
    HEIGHT = 512

    # --- TỌA ĐỘ THỰC ĐỊA (Khu vực Cần Thơ, ĐBSCL) ---
    # Tọa độ góc trên-trái và góc dưới-phải (đơn vị: mét, hệ UTM Zone 48N)
    LEFT   = 560000.0  # Easting (X) góc trái
    BOTTOM = 1070000.0 # Northing (Y) góc dưới
    RIGHT  = 565120.0  # = LEFT + 512 pixel × 10m/pixel
    TOP    = 1075120.0 # = BOTTOM + 512 pixel × 10m/pixel

    # Tạo Affine Transform: ánh xạ pixel (col, row) → tọa độ thực (x, y)
    # from_bounds tự tính ma trận: pixel_size_x = (RIGHT-LEFT)/WIDTH = 10m
    transform = from_bounds(LEFT, BOTTOM, RIGHT, TOP, WIDTH, HEIGHT)

    # Hệ tọa độ: UTM Zone 48N — chuẩn dùng cho Việt Nam với Sentinel-2
    crs = CRS.from_epsg(32648)

    # --- TẠO MA TRẬN GIÁ TRỊ PIXEL (uint16) ---
    # Khởi tạo mảng rỗng cho 2 band
    band_red = np.zeros((HEIGHT, WIDTH), dtype=np.uint16)
    band_nir = np.zeros((HEIGHT, WIDTH), dtype=np.uint16)

    # Chia ảnh 512x512 thành 3 vùng theo chiều dọc:
    # - Cột 0→170: Vùng lúa khỏe (Rice field - healthy)
    # - Cột 171→341: Vùng xâm nhập mặn (Salinity intrusion)
    # - Cột 342→511: Vùng mặt nước / sông (Water body)

    # Thêm noise ngẫu nhiên để gần thực tế hơn (dùng np.random)
    rng = np.random.default_rng(seed=42)  # seed=42 để kết quả lặp lại được

    # Vùng 1: Lúa khỏe mạnh
    noise = rng.integers(-200, 200, size=(HEIGHT, 171))
    band_red[:, 0:171]  = np.clip(800  + noise, 0, 65535).astype(np.uint16)
    band_nir[:, 0:171]  = np.clip(3500 + noise * 2, 0, 65535).astype(np.uint16)

    # Vùng 2: Xâm nhập mặn
    noise = rng.integers(-150, 150, size=(HEIGHT, 171))
    band_red[:, 171:342] = np.clip(1200 + noise, 0, 65535).astype(np.uint16)
    band_nir[:, 171:342] = np.clip(1000 + noise, 0, 65535).astype(np.uint16)

    # Vùng 3: Mặt nước / sông
    noise = rng.integers(-80, 80, size=(HEIGHT, 170))
    band_red[:, 342:]   = np.clip(300 + noise, 0, 65535).astype(np.uint16)
    band_nir[:, 342:]   = np.clip(200 + noise, 0, 65535).astype(np.uint16)

    # --- CẤU HÌNH METADATA FILE OUTPUT ---
    profile = {
        "driver": "GTiff",        # Định dạng GeoTIFF
        "dtype": "uint16",        # Kiểu dữ liệu pixel: số nguyên 16-bit
        "width": WIDTH,
        "height": HEIGHT,
        "count": 1,               # Mỗi file chỉ chứa 1 band (giống Sentinel-2 thật)
        "crs": crs,
        "transform": transform,
    }

    # --- GHI FILE RA ĐĨA ---
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "01_raw")
    os.makedirs(output_dir, exist_ok=True)

    path_red = os.path.join(output_dir, "B04_RED_test.tif")
    path_nir = os.path.join(output_dir, "B08_NIR_test.tif")

    with rasterio.open(path_red, "w", **profile) as dst:
        dst.write(band_red, 1)  # Ghi band_red vào band index 1

    with rasterio.open(path_nir, "w", **profile) as dst:
        dst.write(band_nir, 1)  # Ghi band_nir vào band index 1

    print("✅ Đã tạo dữ liệu test thành công!")
    print(f"   → {path_red}")
    print(f"   → {path_nir}")
    print()
    print("📐 Thông số file:")
    print(f"   Kích thước   : {WIDTH} × {HEIGHT} pixel")
    print(f"   Kiểu dữ liệu : uint16 (0 → 65535)")
    print(f"   Hệ tọa độ   : EPSG:32648 (UTM Zone 48N)")
    print(f"   Pixel size   : 10m × 10m")
    print(f"   Khu vực      : Cần Thơ, ĐBSCL (giả lập)")
    print()
    print("📊 Vùng dữ liệu trong ảnh:")
    print("   Cột  0→170  : Lúa khỏe mạnh  → NDVI dự kiến ≈ +0.60 đến +0.65")
    print("   Cột 171→341 : Xâm nhập mặn   → NDVI dự kiến ≈ -0.10 đến +0.05")
    print("   Cột 342→511 : Mặt nước/sông  → NDVI dự kiến ≈ -0.25 đến -0.15")
    print()
    print("👉 Bước tiếp theo: Mở file src/io/raster_wrapper.py và bắt đầu viết class!")


if __name__ == "__main__":
    create_sentinel2_like_bands()
