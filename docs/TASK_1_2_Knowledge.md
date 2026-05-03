# 📚 KIẾN THỨC NỀN TẢNG — TASK 1.2
> **Mục tiêu**: Hiểu và tự viết 3 hàm trích xuất metadata chuyên sâu từ file ảnh vệ tinh
> **File sẽ viết**: `src/io/raster_wrapper.py` (thêm vào class `RasterWrapper` đã có)
> **3 hàm cần viết**: `get_pixel_size()` · `get_bounds()` · `pixel_to_coords(row, col)`

---

## PHẦN 1 — NHẮC LẠI: AFFINE TRANSFORM LÀ GÌ?

Ở Task 1.1 bạn đã biết `dataset.transform` là một **ma trận 3×3**. Bây giờ hãy hiểu sâu hơn từng ô số trong đó.

### 1.1 Cấu trúc đầy đủ của ma trận Affine

Khi bạn in `dataset.transform` ra Terminal, bạn sẽ thấy dạng:

```
| a   b   c |       | 10.0    0.0   560000.0 |
| d   e   f |   =   |  0.0  -10.0  1075120.0 |
| 0   0   1 |       |  0.0    0.0        1.0 |
```

Mỗi ô có ý nghĩa cụ thể:

| Ký hiệu | Tên gọi | Giá trị trong ảnh test | Ý nghĩa |
|:---:|---|:---:|---|
| `c` | X-origin | `560000.0` | Tọa độ X **thực địa** của **góc trên-trái** (mét) |
| `f` | Y-origin | `1075120.0` | Tọa độ Y **thực địa** của **góc trên-trái** (mét) |
| `a` | X pixel size | `+10.0` | Mỗi bước sang phải 1 cột = thêm 10 mét về phía Đông |
| `e` | Y pixel size | `−10.0` | Mỗi bước xuống 1 hàng = **giảm** 10 mét về phía Bắc |
| `b`, `d` | Rotation | `0.0` | Ảnh không bị xoay (trường hợp thông thường) |

### 1.2 Tại sao `e` âm?

Đây là điểm **gây nhầm lẫn nhiều nhất** với người mới:

```
Hệ tọa độ MẢNG (NumPy):          Hệ tọa độ BẢN ĐỒ (thực địa):
  Row 0  ← Hàng ĐẦU TIÊN            Y tăng lên = về phía Bắc ↑
  Row 1                               Y giảm xuống = về phía Nam ↓
  Row 2
  ...
  Row N  ← Hàng CUỐI CÙNG
```

Row 0 trong mảng = Vị trí **phía Bắc nhất** trên bản đồ (Y lớn nhất).
Row 1 = bước xuống 1 hàng → đi về phía Nam → Y **giảm**.

→ `e = -10.0` vì "đi xuống 1 hàng pixel = giảm 10 mét tọa độ Y".

### 1.3 Truy cập từng phần tử của Transform trong rasterio

```python
t = dataset.transform   # Đây là object kiểu affine.Affine

# Truy cập từng phần tử:
t.a   # pixel size theo X (thường = +10.0)
t.b   # rotation x (thường = 0.0)
t.c   # X tọa độ góc trên-trái
t.d   # rotation y (thường = 0.0)
t.e   # pixel size theo Y (thường = -10.0)
t.f   # Y tọa độ góc trên-trái
```

---

## PHẦN 2 — HÀM 1: `get_pixel_size()`

### 2.1 Pixel size là gì?

Pixel size (hay Ground Sampling Distance — GSD) là **kích thước thực địa của 1 pixel** trên mặt đất.

```
Sentinel-2 Band 4 và Band 8: mỗi pixel = 10m × 10m
                              (1 pixel đại diện cho 10m × 10m diện tích thực)
```

### 2.2 Đọc pixel size từ đâu?

Pixel size nằm ngay trong ma trận Affine:
- **Chiều X** → lấy giá trị tuyệt đối của `transform.a` → `abs(t.a)` = 10.0
- **Chiều Y** → lấy giá trị tuyệt đối của `transform.e` → `abs(t.e)` = 10.0

> Dùng `abs()` vì `e` âm nhưng kích thước pixel luôn là số dương.

### 2.3 Interface hàm cần viết

```python
def get_pixel_size(self) -> tuple:
    """
    Trả về kích thước pixel thực địa (đơn vị: mét).
    Return: (pixel_width, pixel_height) — ví dụ: (10.0, 10.0)
    """
    # TODO: Đọc từ self.transform.a và self.transform.e
    pass
```

**Kết quả kỳ vọng** khi test với file `B04_RED_test.tif`:
```
>>> wrapper.get_pixel_size()
(10.0, 10.0)
```

---

## PHẦN 3 — HÀM 2: `get_bounds()`

### 3.1 Bounding Box là gì?

Bounding Box (hộp giới hạn) là hình chữ nhật **nhỏ nhất** bao quanh toàn bộ ảnh, được mô tả bằng 4 tọa độ thực địa:

```
              ← left ←                    → right →
              |                                   |
TOP (North)   +-----------------------------------+  ↑ top
              |                                   |
              |         TOÀN BỘ ẢNH               |
              |                                   |
BOTTOM(South) +-----------------------------------+  ↓ bottom
```

### 3.2 Công thức tính từ Transform + Width + Height

Đây là phần bạn cần **tự suy luận** từ kiến thức Phần 1:

```
Góc trên-trái  = (c, f)                  ← lấy trực tiếp từ transform
Góc trên-phải  = (c + a × width,  f)
Góc dưới-trái  = (c,              f + e × height)
Góc dưới-phải  = (c + a × width,  f + e × height)
```

Từ đó:
```
left   = c                        ← X góc trái
right  = c + a × width            ← X góc phải
top    = f                        ← Y góc trên (lớn hơn vì f = Y phía Bắc)
bottom = f + e × height           ← Y góc dưới (nhỏ hơn vì e âm)
```

**Ví dụ tính thử** với file test (512×512 pixel, pixel size 10m):
```
left   = 560000.0
right  = 560000.0 + 10.0 × 512  = 565120.0
top    = 1075120.0
bottom = 1075120.0 + (-10.0) × 512 = 1070000.0
```

### 3.3 Interface hàm cần viết

```python
def get_bounds(self) -> dict:
    """
    Tính tọa độ thực địa của 4 cạnh ảnh (bounding box).
    Return: {"left": ..., "right": ..., "top": ..., "bottom": ...}
    Đơn vị: mét (theo hệ tọa độ UTM của CRS)
    """
    # TODO: Tính từ self.transform + self.width + self.height
    pass
```

**Kết quả kỳ vọng** khi test với file `B04_RED_test.tif`:
```
>>> wrapper.get_bounds()
{"left": 560000.0, "right": 565120.0, "top": 1075120.0, "bottom": 1070000.0}
```

> 💡 **Mẹo kiểm tra**: `right - left` phải bằng `width × pixel_size_x` = 512 × 10 = 5120. Và `top - bottom` phải bằng `height × pixel_size_y` = 512 × 10 = 5120.

---

## PHẦN 4 — HÀM 3: `pixel_to_coords(row, col)`

### 4.1 Đây là ứng dụng trực tiếp của phép nhân ma trận

Bạn đã thấy công thức ở Task 1.1:

```
| x_real |   | a  b  c |   | col |
| y_real | = | d  e  f | × | row |
|   1    |   | 0  0  1 |   |  1  |
```

Khai triển ra (vì `b=0`, `d=0`):

```
x_real = a × col + c
y_real = e × row + f
```

→ Đây là 2 phương trình bạn cần implement.

### 4.2 Ví dụ tính thử

Với ảnh test (a=10, c=560000, e=-10, f=1075120):

```
Pixel (row=0, col=0) → Góc trên-trái:
  x = 10 × 0 + 560000  = 560000.0
  y = -10 × 0 + 1075120 = 1075120.0

Pixel (row=0, col=511) → Góc trên-phải:
  x = 10 × 511 + 560000  = 565110.0
  y = -10 × 0 + 1075120  = 1075120.0

Pixel (row=256, col=256) → Tâm ảnh:
  x = 10 × 256 + 560000  = 562560.0
  y = -10 × 256 + 1075120 = 1072560.0
```

### 4.3 Lưu ý quan trọng: Tọa độ trả về là góc pixel hay tâm pixel?

Trong GIS có 2 quy ước:
- **Góc trên-trái của pixel** (rasterio dùng chuẩn này): `(row=0, col=0)` → `(560000, 1075120)`
- **Tâm pixel**: `(row=0, col=0)` → `(560005, 1075115)` = offset thêm nửa pixel

Rasterio mặc định trả về **góc trên-trái**. Khi phỏng vấn, hãy nêu rõ bạn đang dùng quy ước nào.

### 4.4 Thực tế: rasterio đã có sẵn hàm này

```python
# rasterio cung cấp:
x, y = rasterio.transform.xy(transform, row, col)

# Nhưng tự implement bằng công thức trên giúp bạn hiểu bản chất hơn
```

### 4.5 Interface hàm cần viết

```python
def pixel_to_coords(self, row: int, col: int) -> tuple:
    """
    Chuyển đổi tọa độ pixel (row, col) sang tọa độ thực địa (x, y).

    Args:
        row: Chỉ số hàng (0 = hàng trên cùng)
        col: Chỉ số cột (0 = cột trái nhất)

    Return:
        (x, y) — tọa độ thực địa tính bằng mét (hệ UTM)
    """
    # TODO: Áp dụng công thức x = a×col + c  và  y = e×row + f
    pass
```

**Kết quả kỳ vọng**:
```
>>> wrapper.pixel_to_coords(row=0, col=0)
(560000.0, 1075120.0)

>>> wrapper.pixel_to_coords(row=256, col=256)
(562560.0, 1072560.0)
```

---

## PHẦN 5 — PYTHON TYPE HINTS (Cú pháp khai báo kiểu)

Task 1.2 dùng nhiều kiểu trả về khác nhau. Dưới đây là cú pháp cần biết:

```python
# Khai báo kiểu đơn giản
def get_pixel_size(self) -> tuple:      # Trả về tuple
def get_bounds(self) -> dict:           # Trả về dict
def pixel_to_coords(self, row: int, col: int) -> tuple:  # Nhận int, trả tuple

# Khai báo kiểu chi tiết hơn (optional, dùng thư viện typing)
from typing import Tuple, Dict
def get_pixel_size(self) -> Tuple[float, float]:
def get_bounds(self) -> Dict[str, float]:
def pixel_to_coords(self, row: int, col: int) -> Tuple[float, float]:
```

Type Hints **không ảnh hưởng đến runtime** — Python không kiểm tra kiểu lúc chạy. Chúng chỉ giúp IDE (VS Code) gợi ý và giúp người đọc code hiểu nhanh hơn.

---

## PHẦN 6 — CÁCH KIỂM TRA KẾT QUẢ SAU KHI VIẾT XONG

### 6.1 Test thủ công trong Terminal

Mở Python REPL và chạy từng dòng:

```python
import sys
sys.path.insert(0, "src")

from io.raster_wrapper import RasterWrapper

wrapper = RasterWrapper("data/01_raw/B04_RED_test.tif")

# Kiểm tra Task 1.2
print(wrapper.get_pixel_size())         # → (10.0, 10.0)
print(wrapper.get_bounds())             # → {"left": 560000.0, ...}
print(wrapper.pixel_to_coords(0, 0))    # → (560000.0, 1075120.0)
print(wrapper.pixel_to_coords(256, 256))# → (562560.0, 1072560.0)

wrapper.close()
```

### 6.2 Kiểm tra tính nhất quán (Sanity Check)

Sau khi code xong, tự hỏi 3 câu này:

```
1. get_bounds()["right"] - get_bounds()["left"]  == width × get_pixel_size()[0]  ?
   → 565120 - 560000 = 5120  ==  512 × 10.0  ✓

2. get_bounds()["top"] - get_bounds()["bottom"]  == height × get_pixel_size()[1] ?
   → 1075120 - 1070000 = 5120  ==  512 × 10.0  ✓

3. pixel_to_coords(row=0, col=0)  ==  (get_bounds()["left"], get_bounds()["top"])  ?
   → (560000.0, 1075120.0)  ==  (560000.0, 1075120.0)  ✓
```

Nếu cả 3 đều đúng → logic của bạn nhất quán.

---

## 🎯 CHECKLIST — Sẵn sàng code Task 1.2 chưa?

- [ ] Tôi biết `transform.a` = pixel size X và `transform.e` = pixel size Y (âm).
- [ ] Tôi hiểu tại sao `e` âm — vì row tăng xuống = Y tọa độ giảm.
- [ ] Tôi biết công thức: `x = a×col + c` và `y = e×row + f`.
- [ ] Tôi tính được bounding box từ `c, f, a, e, width, height`.
- [ ] Tôi hiểu `pixel_to_coords(0,0)` trả về góc trên-trái (không phải tâm pixel).
- [ ] Tôi biết kiểm tra tính nhất quán bằng 3 câu sanity check ở trên.

---

## 📌 GHI NHỚ CỐT LÕI

| Hàm | Nguồn dữ liệu | Công thức / Logic |
|---|---|---|
| `get_pixel_size()` | `transform.a`, `transform.e` | `(abs(a), abs(e))` |
| `get_bounds()` | `transform.c/f/a/e` + `width/height` | `right = c + a×W`, `bottom = f + e×H` |
| `pixel_to_coords()` | `transform.a/c/e/f` | `x = a×col + c`, `y = e×row + f` |

---

*🔥 Gợi ý: Tự tính tay trên giấy trước khi code. Khi kết quả tay khớp với code → bạn thực sự hiểu, không phải đoán mò.*
