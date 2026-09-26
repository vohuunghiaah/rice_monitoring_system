# AI Tracker

## Lịch sử thay đổi

### 2026-09-25 — Mosaic theo vùng, Study Guide và Manim
- Thêm `src/core/spatial.py`: pixel centers, inverse nearest-neighbor sampling bằng NumPy, block fallback khi vùng nguồn lớn, polygon masking hỗ trợ holes/MultiPolygon.
- Thêm `src/mosaic.py`: EPSG:6933 equal-area; chuyển CRS qua pyproj, ghép first-valid theo khoảng cách ngày/cloud/ID, loại overlap, source_index và provenance.
- Thêm target-date/max-day-gap cho discovery; lưu acquisition date/cloud/effective calibration trong scene summary.
- Thêm CLI mosaic và run --mosaic; AOI GeoJSON, rice class/mask, pixel budget, counts/area/coverage. Giữ toàn AOI trong coverage denominator; báo vùng mask unknown riêng.
- Thêm demo offline và regression tests: tổng 21 tests pass; sau sửa read-only cleanup, test cleanup riêng tiếp tục pass. `pip check` không phát hiện lỗi.
- Viết `docs/STUDY_GUIDE.md` (workflow, thuật ngữ, code excerpts, tradeoffs, bài tập), `docs/WORKSPACE_MAINTENANCE.md`; đồng bộ README và roadmap.
- Viết `scripts/spatial_pipeline_lesson.py` có ba Scene, comments tiếng Việt. Cài Manim Community 0.21.0; render đủ ba video 480p15, kiểm tra khung hình trực quan. Sửa caption Window về đúng col,row; render lại chương đó.
- Dọn .claude, Python/Manim/LaTeX caches; giữ raw/reference rasters, .git/.venv, report/source và video final. Thêm cleanup preview/apply có xác minh đường dẫn, bảo vệ symlink/junction và xử lý OneDrive read-only.
- Bỏ ignore toàn bộ *.tex/*.svg, thay bằng các cache cụ thể. Không sửa các deletion TIFF của người dùng đã có từ trước.
- Dependency bổ sung pyproj>=3.6,<4; Manim pin 0.21.0 ở requirements-viz. Lần cài đầu bị hash mismatch, đã tải lại không dùng cache và cài thành công; không bỏ qua xác minh hash.

### 2026-09-25 — Hoàn thiện pipeline theo tile
- Thêm NDVI float32, masking, palette RGB, windowed pipeline và thống kê/profiling.
- Sửa STAC: pagination, chọn ít mây nhất/tile, <= cloud cover, kiểm tra đủ assets.
- Bổ sung timeout/retry, atomic write, decode validation và cache SHA-256, manifest calibration.
- Sửa geometry cho raster xoay/đảo trục và validation chunk/offset.
- Thêm CLI search/download/run/process; tách animation Manim khỏi ETL script.
- Cập nhật README, roadmap, dependencies và tests; ghi quy tắc tracker vào AGENTS.md.
- Giữ các thay đổi dữ liệu và .claude có sẵn của người dùng.
- Kiểm chứng hoàn tất cho kernel, local full-tile pipeline và STAC discovery; chi tiết ở cuối tài liệu.

## Lỗi còn tồn đọng

- [x] Coverage trước đây chưa có vùng AOI ngoài dữ liệu; mosaic hiện giữ toàn AOI và báo missing coverage.
- [x] Summary trước đây thiếu acquisition date và calibration mặc định thực dùng; đã lưu đầy đủ cho temporal mosaic.
- [x] Cleanup gặp WinError 5 trên directory OneDrive read-only; retry thuộc tính read-only trong allowlist đã test và chạy thành công.
- [ ] Geometry tự cắt/self-intersection chưa được validate/sửa topology; cần GeoJSON hợp lệ từ nguồn dữ liệu.
- [ ] Chưa benchmark mosaic nhiều full tiles/đa CRS ở quy mô tỉnh; correctness đã kiểm tra bằng synthetic fixtures, local demo và CLI.

- [x] Pipeline trước đây chỉ in metadata, chưa tính NDVI/xuất raster.
- [x] Query chỉ một tile gây thiếu vùng xử lý khi bbox giao nhiều tile.
- [x] Ngưỡng cloud cover dùng < thay vì <=.
- [x] Thiếu timeout và integrity check cho download/cache.
- [x] Thiếu kiểm tra assets khiến dictionary band không đầy đủ.
- [x] Pixel size sai với raster xoay; bounds sai khi trục đảo chiều.
- [x] scripts/pipeline_data.py là animation thay vì ETL như README.
- [ ] Chưa xác nhận tải trọn asset từ S3 trong môi trường hiện tại: live SCL GET chậm và chưa trả chunk sau hơn 3 phút nên dừng smoke test; Range GET 1 KiB trả HTTP 206 thành công. STAC discovery, tests timeout/retry/cache và xử lý dữ liệu local đã pass. Cần kiểm thử lại full download trên mạng ổn định.

## Đề xuất cải thiện

- [x] Mosaic nhiều CRS/UTM zones, temporal priority, overlap deduplication và thống kê diện tích trên equal-area grid; kiểm chứng synthetic tests.
- [x] Nhận AOI GeoJSON và categorical rice mask để crop/lọc pixel và thống kê diện tích.
- [ ] Đối chiếu ranh giới/rice mask với ground truth thực địa; NDVI không tự xác nhận loại cây, bệnh hay xâm nhập mặn.
- [ ] Resume tải bằng HTTP Range, lock cho concurrent jobs và chính sách dọn cache/run cũ.
- [ ] Scheduler theo tháng, manifest chỉ rõ kỳ xử lý; cân nhắc COG streaming cho truy vấn AOI nhỏ.
- [ ] Đo peak RSS liên tục và benchmark 256/512/1024 trên nhiều full tiles; hiện đo RSS tại các mốc chunk.
- [ ] Kiểm chứng calibration với nguồn gốc raster; metadata scale/offset khác nhau giữa collection/baseline.

## Kiểm chứng ngày 2026-09-25

- Python 3.11 trong `.venv`; `pip check` không báo dependency lỗi.
- `python -m unittest discover -s tests -v`: 10/10 tests pass, gồm stream gián đoạn/retry, cache hỏng, calibration, all-cloud, SCL partial extent, mismatch grids và edge chunks.
- STAC live search bbox 105/9.5/106/10.5, 2026-01-01/2026-03-31, cloud <=20: 6 tiles.
- Xử lý TIFF thật 10.980 × 10.980, chunk 512: 41,85 s, sampled peak RSS 116,94 MiB; 21.449.966 pixel hợp lệ, mean NDVI 0,292009.
- Đã đối chiếu calibration STAC của scene: scale 0,0001, offset -0,1; TIFF local không lưu calibration (1/0), vì vậy đã truyền override khi chạy.
- Đã mở lại NDVI/RGB kiểm tra kích thước, EPSG:32648, edge windows và internal dataset mask.
- Không coi RSS lấy mẫu là hard memory cap/peak tuyệt đối; chưa xác nhận thống kê lúa/diện tích tỉnh.
- Cài rasterio trên Python 3.14 bị gián đoạn kết nối; đã dùng Python 3.11 venv thành công.
- Affine 3 phát PendingDeprecationWarning cho phép nhân transform trong rasterio; hiện không ảnh hưởng kết quả, cần theo dõi compatibility khi nâng dependency.
- Đã chuyển backlog mosaic/CRS/overlap và các quyết định kiến trúc từ CLAUDE.md sang README, roadmap, tracker; xóa CLAUDE.md theo yêu cầu. Không xóa thư mục cấu hình .claude của người dùng.

- Bổ sung logging scene được chọn, cache hit đã kiểm chứng, download attempts và lỗi mạng để CLI thể hiện tiến độ.

- Đã dừng tiến trình smoke download do chính AI tạo và dọn file tạm tương ứng; không để job tải chạy nền sau khi bàn giao.

- Bàn giao: CLI mosaic demo đã chạy thành công (84 ROI/84 valid pixel); cleanup preview sau cùng không còn mục cần dọn; ba video final và contact sheet đã cập nhật, giữ trong media. Study Guide là tài liệu học chính.
