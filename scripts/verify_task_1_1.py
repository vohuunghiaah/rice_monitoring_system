"""
verify_task_1_1.py
==================
Script KIỂM TRA KẾT QUẢ Task 1.1 — RasterWrapper.

Cách dùng:
  1. Bạn đã viết xong class RasterWrapper trong src/io/raster_wrapper.py
  2. Chạy script này để kiểm tra class của bạn có hoạt động đúng không
  3. Mỗi test sẽ in [PASS] hoặc [FAIL] kèm giải thích

Cách chạy:
  cd rice_monitoring_system
  python scripts/verify_task_1_1.py

Lưu ý: Script này KHÔNG kiểm tra code của bạn, nó kiểm tra KẾT QUẢ.
Nếu class của bạn trả về đúng giá trị → PASS, sai → FAIL + gợi ý sửa.
"""

import sys
import os
import numpy as np

# Thêm thư mục src vào Python path để import được module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# === IMPORT CLASS CỦA BẠN ===
# Sau khi bạn viết xong, dòng dưới đây sẽ tự tìm file của bạn
try:
    from io.raster_wrapper import RasterWrapper
    print("✅ Import RasterWrapper thành công!\n")
except ImportError as e:
    print(f"❌ KHÔNG import được RasterWrapper: {e}")
    print("   → Hãy đảm bảo bạn đã tạo file: src/io/raster_wrapper.py")
    print("   → Và class của bạn tên là: RasterWrapper")
    sys.exit(1)


# === ĐƯỜNG DẪN FILE TEST ===
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
PATH_RED = os.path.join(BASE_DIR, "data", "01_raw", "B04_RED_test.tif")
PATH_NIR = os.path.join(BASE_DIR, "data", "01_raw", "B08_NIR_test.tif")

# Kiểm tra file test tồn tại
for p in [PATH_RED, PATH_NIR]:
    if not os.path.exists(p):
        print(f"❌ Không tìm thấy file test: {p}")
        print("   → Chạy trước: python scripts/generate_test_data.py")
        sys.exit(1)

# ============================================================
# HELPER FUNCTION IN KẾT QUẢ
# ============================================================
pass_count = 0
fail_count = 0

def check(test_name: str, condition: bool, on_pass: str, on_fail: str):
    global pass_count, fail_count
    if condition:
        print(f"  [PASS] {test_name}")
        print(f"         ✓ {on_pass}")
        pass_count += 1
    else:
        print(f"  [FAIL] {test_name}")
        print(f"         ✗ {on_fail}")
        fail_count += 1
    print()

# ============================================================
# TEST GROUP 1: Khởi tạo object
# ============================================================
print("=" * 60)
print("TEST GROUP 1: Khởi tạo RasterWrapper")
print("=" * 60)

try:
    wrapper = RasterWrapper(PATH_RED)
    print("  [INFO] Khởi tạo object thành công.")
    print(f"         Path: {PATH_RED}\n")
    init_ok = True
except Exception as e:
    print(f"  [FAIL] Khởi tạo thất bại: {e}\n")
    init_ok = False

# ============================================================
# TEST GROUP 2: get_metadata()
# ============================================================
print("=" * 60)
print("TEST GROUP 2: Kiểm tra get_metadata()")
print("=" * 60)

if init_ok:
    try:
        meta = wrapper.get_metadata()

        # Test 2.1: Trả về đúng kiểu dict
        check(
            "Kiểu trả về là dict",
            isinstance(meta, dict),
            f"meta là dict với {len(meta)} key",
            "get_metadata() phải trả về kiểu dict, không phải " + str(type(meta))
        )

        # Test 2.2: Có đủ các key bắt buộc
        required_keys = {"width", "height", "crs", "transform", "dtype", "count"}
        missing = required_keys - set(meta.keys())
        check(
            "Metadata có đủ các key bắt buộc",
            len(missing) == 0,
            f"Có đủ keys: {sorted(meta.keys())}",
            f"Còn thiếu các key: {missing}"
        )

        # Test 2.3: Kích thước đúng
        check(
            "width = 512",
            meta.get("width") == 512,
            "width = 512 ✓",
            f"width = {meta.get('width')} (kỳ vọng: 512)"
        )
        check(
            "height = 512",
            meta.get("height") == 512,
            "height = 512 ✓",
            f"height = {meta.get('height')} (kỳ vọng: 512)"
        )

        # Test 2.4: Kiểu dữ liệu đúng
        dtype_val = str(meta.get("dtype", "")).lower()
        check(
            "dtype = uint16",
            "uint16" in dtype_val,
            f"dtype = '{dtype_val}' ✓",
            f"dtype = '{dtype_val}' (kỳ vọng: 'uint16')"
        )

        # Test 2.5: CRS hợp lệ (không None)
        check(
            "CRS không phải None",
            meta.get("crs") is not None,
            f"crs = {meta.get('crs')}",
            "crs = None — bạn chưa đọc CRS từ dataset"
        )

        # Test 2.6: Transform không None
        check(
            "Transform không phải None",
            meta.get("transform") is not None,
            f"transform đọc được ✓",
            "transform = None — bạn chưa đọc transform từ dataset"
        )

        # In giá trị thực để bạn kiểm tra bằng mắt
        print("  [INFO] Giá trị metadata thực tế của bạn:")
        for k, v in meta.items():
            print(f"         {k:12s} = {v}")
        print()

    except Exception as e:
        print(f"  [FAIL] get_metadata() ném ra exception: {e}\n")
        fail_count += 1
else:
    print("  [SKIP] Bỏ qua vì object khởi tạo thất bại.\n")

# ============================================================
# TEST GROUP 3: read_band()
# ============================================================
print("=" * 60)
print("TEST GROUP 3: Kiểm tra read_band()")
print("=" * 60)

if init_ok:
    try:
        arr = wrapper.read_band(1)

        # Test 3.1: Trả về numpy array
        check(
            "Trả về numpy ndarray",
            isinstance(arr, np.ndarray),
            f"Kiểu: np.ndarray ✓",
            f"Kiểu trả về là {type(arr)}, cần là np.ndarray"
        )

        # Test 3.2: Shape đúng (2D: height x width)
        check(
            "Shape = (512, 512)",
            arr.shape == (512, 512),
            f"arr.shape = {arr.shape} ✓",
            f"arr.shape = {arr.shape} (kỳ vọng: (512, 512))\n"
            "         → Đảm bảo bạn dùng dataset.read(band_index) không phải dataset.read()"
        )

        # Test 3.3: Kiểu dữ liệu numpy phải là uint16
        check(
            "numpy dtype = uint16",
            arr.dtype == np.uint16,
            f"arr.dtype = {arr.dtype} ✓",
            f"arr.dtype = {arr.dtype} (kỳ vọng: uint16)"
        )

        # Test 3.4: Có giá trị hợp lệ (không toàn số 0)
        check(
            "Mảng có giá trị khác 0",
            arr.max() > 0,
            f"Giá trị từ {arr.min()} đến {arr.max()} ✓",
            "Toàn bộ mảng là 0 — có thể bạn chưa thực sự đọc dữ liệu"
        )

        # Test 3.5: Giá trị vùng lúa khỏe (cột 0→170) phải nhỏ (~800 RED)
        red_zone_mean = arr[:, 0:171].mean()
        check(
            "Band RED: Vùng lúa khỏe có giá trị thấp (~800)",
            600 < red_zone_mean < 1000,
            f"Mean vùng lúa = {red_zone_mean:.1f} (nằm trong [600, 1000]) ✓",
            f"Mean vùng lúa = {red_zone_mean:.1f} (kỳ vọng: ~800)\n"
            "         → File test có thể bị lỗi, thử chạy lại generate_test_data.py"
        )

        print(f"  [INFO] Thống kê Band RED:")
        print(f"         arr.min()  = {arr.min()}")
        print(f"         arr.max()  = {arr.max()}")
        print(f"         arr.mean() = {arr.mean():.2f}")
        print(f"         arr.shape  = {arr.shape}")
        print()

    except Exception as e:
        print(f"  [FAIL] read_band() ném ra exception: {e}\n")
        fail_count += 1
else:
    print("  [SKIP] Bỏ qua vì object khởi tạo thất bại.\n")

# ============================================================
# TEST GROUP 4: close()
# ============================================================
print("=" * 60)
print("TEST GROUP 4: Kiểm tra close()")
print("=" * 60)

if init_ok:
    try:
        wrapper.close()
        print("  [INFO] close() chạy không báo lỗi ✓\n")

        # Test: Sau khi close, gọi read_band lại phải bị lỗi (file đã đóng)
        try:
            wrapper.read_band(1)
            print("  [WARN] Sau khi close(), vẫn read_band() được.")
            print("         → Cân nhắc: class của bạn có nên tự set self.dataset = None?")
            print()
        except Exception:
            check(
                "Sau close(), read_band() ném exception (đúng hành vi)",
                True,
                "File đã đóng, gọi read tiếp báo lỗi → Đúng! ✓",
                ""
            )
    except Exception as e:
        print(f"  [FAIL] close() ném ra exception: {e}\n")
        fail_count += 1
else:
    print("  [SKIP] Bỏ qua vì object khởi tạo thất bại.\n")

# ============================================================
# TỔNG KẾT
# ============================================================
total = pass_count + fail_count
print("=" * 60)
print("TỔNG KẾT")
print("=" * 60)
print(f"  PASS : {pass_count}/{total}")
print(f"  FAIL : {fail_count}/{total}")
print()

if fail_count == 0:
    print("🎉 Xuất sắc! Tất cả test đều PASS.")
    print("   → Bạn đã sẵn sàng chuyển qua Task 1.2 (đọc CRS & Transform chi tiết hơn)")
elif fail_count <= 2:
    print("💪 Gần xong rồi! Sửa các test FAIL ở trên là done.")
else:
    print("🔧 Còn một số vấn đề cần sửa.")
    print("   → Đọc kỹ phần [FAIL] và gợi ý bên dưới mỗi test.")
    print("   → Bạn có thể hỏi tôi nếu không hiểu thông báo lỗi nào.")
print()
print("📌 Sau khi PASS hết, đánh dấu [x] vào Task 1.1 trong EXECUTION_ROADMAP.md")
