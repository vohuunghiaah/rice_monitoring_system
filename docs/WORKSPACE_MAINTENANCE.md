# Workspace maintenance

## Đã dọn trong lần hoàn thiện này

- `.claude/`: cấu hình assistant cũ, đã xóa theo yêu cầu.
- `__pycache__/` ở gốc, scripts, src và tests.
- `docs/report.aux`, `.log`, `.out`, `.toc`: build artifacts của `report.tex`.
- `media/Tex/`, `media/texts/`: cache render Manim.
- `partial_movie_files/` của video cũ và bài học mới: các đoạn trung gian; video hoàn chỉnh vẫn còn.
- Không phát hiện `.DS_Store` trong các thư mục được quét.

Một số thư mục OneDrive có thuộc tính read-only. Cleanup tool đã được sửa và kiểm thử để gỡ thuộc tính này chỉ trên cache được chọn, rồi retry; không thay ACL. Trước mỗi recursive delete, tool resolve đường dẫn, xác nhận nó nằm bên trong workspace và không phải workspace root. Symlink/junction bị bỏ qua.

## Giữ lại vì có giá trị

| Path | Lý do |
|---|---|
| `.git/` | Lịch sử phiên bản, tuyệt đối không phải cache |
| `.venv/` | Interpreter/dependencies đang chạy; không commit/deploy nguyên thư mục |
| `data/` | Raw, scene manifests, processed outputs, demo; không xóa theo tuổi tự động |
| `image_test/` | Input/reference raster của người dùng, không coi là file rác |
| `docs/report.tex`, `docs/report.pdf`, `docs/img/` | Tài liệu nguồn và artifacts học tập |
| `media/videos/**/<Scene>.mp4` | Các video hoàn chỉnh |
| `scripts/pipeline_animation.py` | Bài animation 3D cũ; cần LaTeX, tách biệt script mới |

`.gitignore` đã bỏ hai rule rộng `*.tex` và `*.svg`, thay bằng ignore cache cụ thể. Source LaTeX/SVG không nên bị ẩn khỏi version control chỉ vì cùng extension với file sinh tự động.

## Chạy lại khi cần

```powershell
.venv\Scripts\python scripts/clean_workspace.py
.venv\Scripts\python scripts/clean_workspace.py --apply
```

Lệnh đầu chỉ preview. Lệnh thứ hai chỉ xóa allowlist; không duyệt `.git`, `.venv`, `data`, `image_test`. Chạy sau khi tests/render kết thúc để tránh xóa cache của tác vụ đang chạy. Tests xác nhận preview không xóa, apply giữ raw/reference/final video, và xử lý directory read-only.

`data/` cần retention policy riêng: xác định summary nào đang tham chiếu từng run, sao lưu nếu cần, rồi mới xóa run không còn dùng. Không dùng `Remove-Item -Recurse data` để dọn nhanh. `.part` trong raw cũng không được tool tự xóa vì có thể thuộc download đang chạy.

Các file TIFF đã bị xóa khỏi gốc trong trạng thái Git trước khi AI làm việc được giữ nguyên trạng thái; lần cleanup này không xóa thêm dữ liệu raster của người dùng.
