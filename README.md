# Rice Monitoring System

Pipeline Sentinel-2 L2A: STAC → tải B04/B08/SCL → calibration + lọc mây → NDVI theo chunk → mosaic khác CRS → AOI/rice mask → GeoTIFF và thống kê diện tích/coverage.

Để học kiến trúc và cách đọc code, bắt đầu với [Study Guide](docs/STUDY_GUIDE.md). Tài liệu có workflow, khái niệm, deep dive code, ví dụ số và bài tập. [Roadmap](EXECUTION_ROADMAP.md) theo dõi chức năng; [AI Tracker](AI_TRACKER.md) ghi thay đổi và hạn chế.

## Cài đặt và chạy demo offline

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts/demo_pipeline.py
.venv\Scripts\python -m unittest discover -s tests -v
```

Demo ghi vào `data/demo/`: hai tile giả lập, SCL có mây, polygon và rice mask minh họa, NDVI/RGB, mosaic và `source_index.tif`. Dữ liệu demo không phải bản đồ lúa thực tế.

Python 3.11+; runtime NumPy/rasterio/requests/pystac-client/psutil/pyproj. Manim là dependency tùy chọn. Các lệnh sau dùng Python trong `.venv` để tránh nhầm interpreter.

## Chạy dữ liệu thật

Tìm scene trước khi tải nhiều GB:

```powershell
.venv\Scripts\python -m src.main search --bbox 105 9.5 106 10.5 --dates 2026-02-01/2026-02-07 --cloud-cover 20 --target-date 2026-02-03 --max-day-gap 3
```

Tải, tính từng tile và mosaic trong một lệnh:

```powershell
.venv\Scripts\python -m src.main run --bbox 105 9.5 106 10.5 --dates 2026-02-01/2026-02-07 --cloud-cover 20 --target-date 2026-02-03 --max-day-gap 3 --mosaic --chunk-size 512
```

Bổ sung `--aoi path/to/province.geojson --rice-mask path/to/rice.tif --rice-class 1` khi có ranh giới và mask thực tế. Bbox discovery phải bao phủ AOI; CLI không tự suy ra bbox từ polygon. Mã class của rice mask do người cung cấp dữ liệu quyết định.

`download` có cùng tham số discovery nhưng chỉ tải và ghi manifest. Không truyền target date: chọn ít mây nhất cho mỗi tile. Có target date: ưu tiên gần ngày, rồi ít mây. Query lấy tất cả trang, ngưỡng cloud `<=`; scene ngoài max-day-gap bị loại. Mỗi tile vẫn chỉ giữ một scene. `--max-day-gap 0` dùng đúng ngày; gap 3 có thể tạo composite chênh tối đa 6 ngày giữa nguồn.

Earth Search public assets không cần tài khoản. Bbox là west/south/east/north trong WGS84, không hỗ trợ qua dateline. `python scripts/pipeline_data.py ...` cung cấp cùng CLI.

## Dữ liệu local và calibration

Ưu tiên manifest do downloader tạo:

```powershell
.venv\Scripts\python -m src.main process --manifest data/01_raw/SCENE_ID.json
```

Với bộ TIFF có sẵn trong workspace, calibration đã đối chiếu STAC:

```powershell
.venv\Scripts\python -m src.main process --red data/01_raw/S2C_48PWS_20260203_0_L2A_B04.tif --nir data/01_raw/S2C_48PWS_20260203_0_L2A_B08.tif --scl data/01_raw/S2C_48PWS_20260203_0_L2A_SCL.tif --scene-id S2C_48PWS_20260203_0_L2A --acquired-at 2026-02-03 --scale 0.0001 --offset -0.1
```

Scale/offset là thuộc tính của nguồn; không copy giá trị ví dụ cho mọi raster. Local mode dùng override rồi metadata TIFF (thiếu thì 1/0). Manifest tải mới lưu `raster:bands`. Xem [Earth Search metadata](https://github.com/Element84/earth-search). Summary cũ không có `datetime` phải được tạo lại từ manifest hoặc local input có `--acquired-at` trước khi mosaic; không đoán ngày từ tên file.

RED/NIR phải cùng grid/CRS. SCL cùng CRS và lưới song song, resolution bằng hoặc thô hơn. Giữ SCL 4/5/6/7; loại mây/bóng/tuyết/nodata. NumPy tự tính NDVI, masking, nearest-neighbor và point-in-polygon. pyproj chỉ chuyển tọa độ; rasterio chỉ raster I/O.

## Mosaic những scene đã xử lý

```powershell
.venv\Scripts\python -m src.main mosaic --summaries data/demo/processed/demo_1_summary.json data/demo/processed/demo_2_summary.json --target-date 2026-02-03 --aoi data/demo/illustrative_aoi.geojson --rice-mask data/demo/illustrative_rice_mask.tif --resolution 10 --output-dir data/demo/mosaic_cli
```

Đầu ra dùng EPSG:6933 equal-area, resolution mét. Priority: khoảng cách ngày → cloud cover → scene ID. First valid wins tại mỗi pixel; NaN của scene ưu tiên cho phép scene tiếp theo lấp vào. `source_index.tif` và danh sách `sources` truy nguồn pixel. Không cộng diện tích các tile chồng lấn.

GeoJSON nhận Polygon/MultiPolygon/Feature/FeatureCollection WGS84 (lon/lat), hỗ trợ holes; ring phải đóng và không qua dateline; giới hạn latitude ±85°. Geometry phải hợp lệ về topology. Crop dùng pixel center, có sai số biên theo resolution. `roi_area_ha` là diện tích AOI/rice class, `observed_area_ha` là phần có NDVI hợp lệ. Coverage giữ cả vùng AOI thiếu ảnh; rice-mask nodata được báo riêng trong `mask_unknown_pixels`.

Bộ đếm/diện tích đã kiểm chứng bằng synthetic tests. Độ đúng phân loại lúa/diện tích thực địa cần mask và ground truth được xác thực. NDVI và màu không tự chứng minh năng suất, hạn, mất mùa hay xâm nhập mặn.

## Outputs và vận hành

- `data/01_raw`: TIFF, receipt `.tif.json` (URL/SHA-256), manifest scene.
- `data/03_processed/<scene>-<run>/`: `ndvi.tif` float32 nodata NaN, `rgb.tif` có internal validity mask.
- `<scene>_summary.json`: metadata, acquisition date, calibration thực dùng, statistics, đường dẫn run hoàn tất.
- `mosaic/<run>/`: NDVI/RGB/source_index; `mosaic_summary.json` là completion marker.

Tải có timeout/retry, file tạm và atomic replace, kiểm Content-Length, decode block, hash. Cache chỉ dùng khi URL/hash khớp; file cũ thiếu receipt phải tải lại. Chưa resume theo byte hoặc lock nhiều process. Chạy tuần tự mỗi output directory. Full download S3 còn cần xác nhận trên kết nối ổn định; unit tests không thay thế kiểm thử mạng thật.

Processing dùng chunk (1–2048), GDAL cache 32 MiB; source sampling chuyển sang block khi rectangle đọc quá lớn. Mosaic giới hạn 128 inputs và mặc định 500 triệu output pixels; dùng AOI/resolution hoặc `--max-pixels` để điều chỉnh. `sampled_peak_rss_mb` không phải hard memory cap/peak tuyệt đối. Chưa có chính sách tự xóa raw/run cũ.

Task Scheduler/cron có thể gọi CLI với interpreter, cwd, ngày và bbox explicit. Exit code 0 thành công, 1 lỗi runtime, 2 sai tham số. Lịch chạy hệ thống chưa được tự cài.

## Bài học Manim

```powershell
.venv\Scripts\python -m pip install -r requirements-viz.txt
.venv\Scripts\python -m manim -ql scripts/spatial_pipeline_lesson.py WindowedNDVI GridAlignment MosaicAndArea
.venv\Scripts\python -m manim -qh scripts/spatial_pipeline_lesson.py GridAlignment
```

Script mới chạy bằng **Manim Community 0.21.0**, Text/Pango, không cần LaTeX. Ba video: chunk/calibration; inverse mapping/SCL; mosaic/provenance/area. Bản preview ở `media/videos/spatial_pipeline_lesson/480p15/`. Script có comment tiếng Việt để tự sửa timeline. `scripts/pipeline_animation.py` là bài 3D cũ, cần LaTeX và cấu hình render riêng; được giữ như tài liệu học bổ sung.

## Cấu trúc và dọn workspace

```text
src/io/                  discovery, download, raster wrapper
src/core/                NDVI, NumPy sampling, polygon masking
src/viz/                 NDVI color palette
src/pipeline.py          một scene, windowed processing
src/mosaic.py            nhiều scene, common grid, area
src/main.py              CLI
scripts/demo_pipeline.py offline example
scripts/clean_workspace.py preview/apply cleanup
scripts/spatial_pipeline_lesson.py Manim lesson
docs/STUDY_GUIDE.md       tài liệu học kiến trúc và code
tests/                   synthetic raster + mocked network regressions
```

```powershell
.venv\Scripts\python scripts/clean_workspace.py
.venv\Scripts\python scripts/clean_workspace.py --apply
```

Cleanup chỉ nhắm cache đã biết, `.claude` và LaTeX build artifacts; không duyệt `.git`, `.venv`, `data`, `image_test`, không xóa video final/report/source. Xem [Cleanup notes](docs/WORKSPACE_MAINTENANCE.md). `.gitignore` không còn chặn toàn bộ source `.tex`/`.svg`.
