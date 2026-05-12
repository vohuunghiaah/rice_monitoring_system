# Rice Monitoring System

## Overview
Hệ thống phân tích và giám sát thảm thực vật (cụ thể là lúa) dựa trên dữ liệu viễn thám đa phổ. Dự án tập trung vào việc xử lý mảng dữ liệu không gian (spatial data arrays) kích thước lớn, tối ưu hóa quá trình cấp phát bộ nhớ khi đọc/ghi file GeoTIFF, và trích xuất chỉ số thực vật (NDVI) kết hợp lọc nhiễu khí quyển.

## Data Source
Dữ liệu đầu vào được thu thập từ [Copernicus Data Space Ecosystem](https://browser.dataspace.copernicus.eu/).

*   **Satellite:** Sentinel-2 (MultiSpectral Instrument - MSI)
*   **Processing Level:** Level-2A (Bottom of Atmosphere - BOA reflectance)
*   **Cloud Cover Constraint:** `<= 20%`
*   **Target Bands:** B04 (Red), B08 (NIR), SCL (Scene Classification Layer)

## System Architecture & Folder Structure
Kiến trúc dự án được thiết kế theo hướng module hóa, tách biệt tầng I/O, core logic và visualization.

```text
rice_monitoring_system/
├── .gitattributes
├── .gitignore
├── EXECUTION_ROADMAP.md      # Kế hoạch phát triển, milestones (Python -> C++)
├── README.md
├── requirements.txt          # Chứa các dependencies (rasterio, numpy,...)
├── data/
│   ├── 01_raw/               # Chứa file .tif gốc tải từ Copernicus
│   ├── 02_intermediate/      # Dữ liệu tạm thời (đã cắt, mask mây SCL)
│   └── 03_processed/         # Kết quả đầu ra (bản đồ NDVI, thống kê)
├── docs/                     # Tài liệu kỹ thuật, kiến trúc, math formulas (LaTeX)
├── media/                    # Hình ảnh, video minh họa (Manim exports)
├── scripts/
│   └── pipeline_data.py      # Entry point để chạy toàn bộ luồng ETL
└── src/
    ├── core/                 # Chứa thuật toán tính toán (NDVI, math ops)
    │   └── __init__.py
    ├── io/                   # Tầng xử lý đọc/ghi I/O
    │   ├── __init__.py
    │   └── raster_wrapper.py # Wrapper quản lý rasterio, window chunking, affine matrices
    ├── viz/                  # Trực quan hóa dữ liệu (matplotlib, manim)
    │   └── __init__.py
    └── main.py               # Khởi tạo và liên kết các module