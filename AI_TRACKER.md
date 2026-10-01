# AI Tracker

## Lịch sử thay đổi

### 2026-10-01 — Chẩn đoán log Colab của dự án ngoài workspace (ProtoEnergy-IDS)
- Log người dùng cung cấp cho thấy Stage 4 dừng tại `openmax.py:28`, `import libmr`, với `ModuleNotFoundError`; các worker được liệt kê cùng lỗi thiếu dependency.
- Hướng dẫn cài `libmr==0.1.9` trong runtime Colab và kiểm tra import trước khi chạy lại Stage 4. Chưa truy cập runtime hoặc sửa mã ProtoEnergy-IDS; chưa xác nhận khắc phục thành công.

### 2026-09-28 — Hardening nhánh change detection
- Loại GDAL Env bị suspend qua yield; kiểm chứng xen kẽ hai iterator và đóng khác thứ tự không làm hỏng môi trường caller.
- Quality mask observed chỉ chấp nhận 0/1 để ngăn raw SCL bị hiểu nhầm là clear. Thêm quality_radius bằng NumPy integral sums, đọc quality context mở rộng để erosion không phụ thuộc core size.
- Siết contract buffer/shape/dtype, tên kênh, NDVI pair, calibration float32, finite Affine, model input/output và loss parameters/masks; spectral overflow trả invalid thay vì inf.
- Writer kiểm tra cả sub_affine/core_affine, scene/channel contract, thứ tự core và coverage hoàn chỉnh; khóa output, bảo vệ input/hardlink và từ chối sidecar cũ.
- CLI xác minh schema manifest/checkpoint, finite weights/threshold, ngăn ghi đè manifest/checkpoint; GeoTIFF lưu hash SHA-256 manifest/checkpoint và phiên bản PyTorch.
- Metrics bổ sung precision, recall, threshold và số histogram bins. Đồng bộ README, manifest mẫu và technical report.
- Kiểm chứng cuối: `.venv/Scripts/python -W error::RuntimeWarning -m unittest discover -s tests -v`: 40/40 pass, không skip, 6,896 s. `git diff --check` không báo whitespace lỗi. Không thay đổi learner self-assessment.

### 2026-09-28 — Pipeline Siamese change detection và technical report
- Thêm Module 1 `src/raster_engine.py`: NumPy window buffers, calibration in-place, spectral kernel, halo, joint validity và data contract bảo toàn CRS/Affine; từ chối input lệch grid.
- Thêm `src/dataset_bridge.py`: generator PyTorch batch-one chia sẻ storage NumPy ở CPU, buffer có ownership riêng; không tuyên bố zero-copy khi chuyển GPU.
- Thêm Module 2 `src/vision_core.py`: shared Siamese encoder, absolute feature differences, decoder nhị phân, masked Focal BCE + Tversky tính float32 từ logits.
- Thêm orchestration/reconstruction GeoTIFF atomic, class 255 unknown, metrics global IoU và histogram AP, CLI kiểm tra checkpoint/channel order, dependency vision riêng và manifest mẫu.
- Viết `docs/CHANGE_DETECTION_REPORT.md`: trách nhiệm module, memory/halo/affine, tradeoffs kiến trúc và loss, metric conventions, thiết kế SAR và giới hạn chưa kiểm chứng; cập nhật README.
- Cài PyTorch 2.14.0+cpu vào `.venv`; `pip check`: không có dependency lỗi. Không sửa các ghi chú tracker đã có của người dùng.
- `python -m unittest discover -s tests -v`: 32/32 pass (12,710 s), gồm 11 tests mới, không skip. Kiểm tra end-to-end CLI bằng checkpoint synthetic, storage sharing, gradient cực trị, serialization và equivalence tại seam với halo=32.
- Còn PendingDeprecationWarning từ Affine `*` (cả code hiện có/rasterio); không ảnh hưởng test hiện tại. Chưa benchmark full-scene DL hoặc GPU, chưa huấn luyện/đánh giá lúa thực địa.

### 2026-09-26 — Đánh giá tổng thể project
- Kiểm tra toàn bộ cấu trúc: src (core/io/viz), pipeline, mosaic, main CLI, scripts, tests, docs, media.
- Chạy `unittest discover`: 21/21 tests pass (0.9s). Có PendingDeprecationWarning cho Affine `*` operator.
- Xác nhận tất cả 6 giai đoạn trong EXECUTION_ROADMAP đã hoàn thành phần core.
- Phần chưa xong thuộc backlog vận hành (HTTP resume, ground truth validation, full S3 download, benchmark tỉnh).
- Không phát hiện bug blocking hoặc chức năng cốt lõi bị thiếu.

### 2026-09-26 — Push lên GitHub
- Thêm `image_test/` vào `.gitignore` (chứa file `.tif` ~123MB vượt giới hạn 100MB của GitHub).
- Commit 34 files changed (3024 insertions, 986 deletions): spatial pipeline, NDVI engine, mosaic, heatmap viz, tests, docs, media videos/images.
- Xóa 3 file `.tiff` lớn ở root và `CLAUDE.md` khỏi git tracking.
- Push thành công lên `origin/main` tại `https://github.com/vohuunghiaah/rice_monitoring_system.git`.

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

- [ ] Ngoài workspace — ProtoEnergy-IDS trên Colab: Stage 4 thiếu `libmr`; chờ kiểm chứng cài đặt/import và chạy lại tại runtime người dùng.

- [x] Raw SCL có thể bị coi là quality clear; từ chối giá trị observed ngoài 0/1, regression test pass.
- [x] GDAL Env của generator không an toàn khi iterator xen kẽ; không giữ Env qua yield, regression test pass.
- [x] Stream thiếu core hoặc sub_affine sai có thể publish raster không đủ coverage; writer xác minh contract/thứ tự/số core trước publish.
- [x] CLI có thể ghi đè checkpoint/manifest và nhận width thập phân hoặc tham số vô hạn; đã kiểm tra schema, đường dẫn, finite parameters.
- [x] Validity số/NaN bị ép thành bool âm thầm và logits vô hạn có thể sigmoid thành xác suất hợp lệ; đã từ chối sai dtype/nonfinite logits.
- [x] Hai writer cùng output hoặc sidecar cũ có thể làm sai output; thêm exclusive lock và kiểm tra sidecar, failure giữ nguyên file cũ.

- [x] Vòng đời GDAL Env của generator và writer từng đóng sai thứ tự khi stream kết thúc; đã đặt môi trường ngoài bao trọn orchestration, regression reconstruction/CLI pass.
- [ ] Nhánh DL chưa có checkpoint/ground truth lúa thực địa; không sử dụng kết quả synthetic làm bản đồ biến động thực tế.
- [x] Thiếu tùy chọn loại vùng giáp mây; đã thêm quality_radius với NumPy erosion, kiểm chứng độc lập kích thước core. Đánh giá bán kính tối ưu thực địa vẫn chưa thực hiện.
- [ ] Chưa đánh giá chất lượng thực địa vùng giáp mây và lựa chọn quality_radius; mặc định 0 không tự áp dụng erosion.

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

- [ ] Ngoài workspace — ProtoEnergy-IDS: thêm dependency OpenMax vào cell setup và kiểm tra import trước khi khởi chạy loạt worker để tránh lặp cùng lỗi qua nhiều seed.

- [ ] Bổ sung quy trình vận hành kiểm tra PID và dọn stale output lock sau process crash; không tự xóa lock có thể đang được job khác dùng.
- [ ] Đóng gói preprocessing/training provenance theo schema version, kiểm tra tương thích calibration policy giữa train và inference; hash manifest/checkpoint hiện phục vụ truy vết, chưa thay thế kiểm chứng ngữ nghĩa.

- [ ] Đánh giá DL theo spatial/seasonal splits, chọn threshold trên validation, lưu calibration/quality policy/data hashes cùng checkpoint; hiện CLI chỉ xác minh architecture/channels/state shapes.
- [ ] Benchmark peak RSS/throughput full tile và GPU; khóa dependency theo môi trường triển khai, giới hạn worker/prefetch dựa trên memory budget.
- [ ] Bổ sung multimodal optical/SAR encoders và validity theo modality; nối thêm VV/VH đơn thuần chưa tận dụng được SAR tại vùng optical bị che mây.
- [ ] Nếu cần phân biệt mất/mở rộng lúa, bổ sung semantic head theo thời điểm hoặc signed temporal features và nhãn phù hợp.

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
