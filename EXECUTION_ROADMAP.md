# Lộ trình thực thi

Cập nhật: 2026-09-25. Pipeline xử lý từng scene và mosaic nhiều tile; NumPy thực hiện numerical kernels, masking, nearest-neighbor, point-in-polygon. Rasterio dùng cho raster I/O; pyproj/PROJ chỉ chuyển tọa độ CRS.

## Giai đoạn 1 — Dataflow và I/O

- [x] 1.1 RasterWrapper, metadata, đọc band, context manager.
- [x] 1.2 Pixel size, bounds ảnh xoay/đảo trục, pixel coordinates.
- [x] 1.3 Windowed reading và edge chunks, validation.
- [x] STAC pagination, cloud <=, lựa chọn một scene/tile; thêm ưu tiên ngày mục tiêu.
- [x] Timeout/retry, atomic download, block decode validation, SHA-256 cache, manifest.

## Giai đoạn 2 — Core engine

- [x] 2.1 NDVI float32, tránh uint16 underflow.
- [x] 2.2 Mask vectorized: denominator 0, nonfinite, nodata, SCL.
- [x] 2.3 Bounded chunks, calibration scale/offset và effective calibration trong summary.

## Giai đoạn 3 — Visualization

- [x] 3.1 NumPy palette interpolation [-1,1] → RGB.
- [x] 3.2 RGB GeoTIFF có internal validity mask.
- [x] Bài học Manim Community 0.21.0: WindowedNDVI, GridAlignment, MosaicAndArea; đã render preview cả ba.

## Giai đoạn 4 — Pipeline và kiểm chứng

- [x] 4.1 CLI search/download/run/process và output summaries.
- [x] 4.2 Chunk-wise read/compute/write, SCL khác resolution.
- [x] 4.3 Wall time, sampled RSS và streaming statistics.
- [x] CLI mosaic; run --mosaic nối download → process → mosaic.
- [x] 21 regression tests: kernel, I/O, network mocks, CRS, overlap, AOI/rice mask, CLI và cleanup.
- [x] Demo offline có hai tile, mây, polygon và mask giả lập; CLI mosaic đã chạy.

## Giai đoạn 5 — Mở rộng vùng nghiên cứu

- [x] CRS harmonization giữa UTM zones trên destination grid EPSG:6933 equal-area.
- [x] NumPy nearest-neighbor inverse mapping; giới hạn source read rectangle và block fallback.
- [x] Overlap deduplication: first valid theo gần ngày → cloud → ID; lưu source_index và provenance.
- [x] Target date/max-day-gap cho discovery và mosaic; báo nguồn bị loại.
- [x] GeoJSON Polygon/MultiPolygon/holes, pixel-center AOI masking và categorical rice mask.
- [x] Thống kê diện tích/coverage kiểm chứng bằng synthetic tests; AOI thiếu ảnh và mask unknown được báo riêng.
- [ ] Đối chiếu rice mask và diện tích với ground truth thực địa. Cần dữ liệu xác thực bên ngoài; không đánh dấu hoàn tất bằng unit test.

## Giai đoạn 6 — Học tập và bảo trì

- [x] Study Guide: workflow, khái niệm, deep dive code, tradeoffs và bài tập.
- [x] Cleanup tool mặc định preview, --apply xóa cache allowlist; bảo vệ dữ liệu/source/final artifacts.
- [x] Dọn .claude, Python/Manim/LaTeX caches; bỏ ignore rộng *.tex/*.svg.
- [x] Đồng bộ README, roadmap, tracker; giữ bài animation 3D cũ như reference.

## Backlog vận hành

- [ ] Xác nhận tải full S3 asset trên kết nối ổn định; STAC và mocked download tests đã xác nhận.
- [ ] HTTP Range resume, concurrent-job locking, retention policy cho raw/run cũ.
- [ ] Scheduler theo kỳ thực tế; hiện cung cấp CLI để Task Scheduler/cron gọi.
- [ ] Temporal compositing nhiều observation/tile, uncertainty và quality flags theo pixel.
- [ ] Continuous peak RSS profiling và benchmark nhiều full tiles.

## Mock interview — tự đánh giá của người học

- [ ] Q1: RAM ảnh uint16 và giới hạn container 256 MB.
- [ ] Q2: Divide-by-zero qua masking/vectorization.
- [ ] Q3: Chi phí casting float64 và intermediate arrays.
- [ ] Q4: I/O bottleneck khi multiprocessing.
- [ ] Q5: Row-major/column-major và cache locality.

Chỉ người học đánh dấu các câu phỏng vấn sau khi tự đánh giá. Study Guide có ví dụ và bài tập để luyện.
