# 📚 KIẾN THỨC NỀN TẢNG — TASK 1.3
> **Mục tiêu**: Đọc ảnh lớn theo từng mảnh nhỏ (Chunk) mà không cần nạp toàn bộ vào RAM
> **File sẽ viết**: `src/io/raster_wrapper.py` — thêm method `read_chunk()` vào class `RasterWrapper`
> **Vấn đề cần giải quyết**: 1 band Sentinel-2 thật = ~230MB RAM. Không thể `.read()` toàn bộ.

---

## PHẦN 1 — VẤN ĐỀ BỘ NHỚ (Nhắc lại để hiểu động lực)

### 1.1 Tính toán RAM thực tế

```
Sentinel-2 thật (10m resolution):
  1 band = 10980 × 10980 pixel × 2 bytes/pixel (uint16)
         = 241,120,800 bytes ≈ 230 MB

4 band cùng lúc (B02, B03, B04, B08):
         ≈ 920 MB  →  gần 1 GB chỉ để đọc dữ liệu thô
```

Nếu bạn dùng `dataset.read(1)` → Python yêu cầu hệ điều hành cấp phát 230MB **liên tục** một lúc.
Với máy tính 8GB RAM và OS đang dùng ~4GB cho hệ thống → còn 4GB trống, nhưng vẫn gây ra:
- **Memory pressure** → OS phải swap ra ổ cứng
- **Không thể xử lý song song nhiều file** cùng lúc
- **Crash** nếu chạy trong container Docker bị giới hạn RAM

### 1.2 Giải pháp: Chunked / Windowed Reading

Thay vì đọc toàn bộ ảnh, đọc từng **cửa sổ nhỏ (Window)** 256×256 hoặc 512×512 pixel:

```
Toàn bộ ảnh 10980×10980:
+------------------------------------------+
| Chunk(0,0)  | Chunk(0,1)  | Chunk(0,2)  |
| 256×256     | 256×256     | 256×256     |
+------------------------------------------+
| Chunk(1,0)  | Chunk(1,1)  | Chunk(1,2)  |
|             |             |             |
+------------------------------------------+
  ↑ Xử lý từng chunk một, đọc xong tính toán xong → bỏ đi → đọc chunk tiếp
```

RAM tối đa dùng tại bất kỳ thời điểm nào = 256 × 256 × 2 bytes = **~128 KB** thay vì 230 MB.

---

## PHẦN 2 — `rasterio.windows` — Công cụ đọc theo vùng

### 2.1 `Window` object là gì?

`rasterio.windows.Window` mô tả một **hình chữ nhật** trong không gian pixel của ảnh:

```python
import rasterio
from rasterio.windows import Window

# Window(col_off, row_off, width, height)
# col_off: Cột bắt đầu (tính từ 0, từ trái sang)
# row_off: Hàng bắt đầu (tính từ 0, từ trên xuống)
# width:   Số cột muốn đọc
# height:  Số hàng muốn đọc

w = Window(col_off=0, row_off=0, width=256, height=256)
# → Đọc góc trên-trái, kích thước 256×256 pixel
```

### 2.2 Đọc dữ liệu theo Window

```python
with rasterio.open("file.tif") as ds:
    window = Window(0, 0, 256, 256)
    chunk = ds.read(1, window=window)
    # chunk.shape = (256, 256)  ← Chỉ nạp 256×256 pixel, không phải toàn bộ ảnh
```

### 2.3 Tính toán số chunk cần thiết

```
Ảnh kích thước: width=10980, height=10980
Chunk size: 256×256

Số chunk theo chiều ngang: ceil(10980 / 256) = 43
Số chunk theo chiều dọc:   ceil(10980 / 256) = 43
Tổng số chunk: 43 × 43 = 1849 chunk
```

> **Lưu ý**: Chunk cuối mỗi hàng và mỗi cột sẽ **nhỏ hơn** 256 (phần dư). Code phải xử lý đúng.

Ví dụ cụ thể:
```
Width = 10980, chunk_size = 256
Chunk cuối cùng theo X: col_off = 43×256 = 11008 > 10980 → KHÔNG ĐỌC ĐƯỢC!

Xử lý đúng: width_actual = min(chunk_size, total_width - col_off)
             = min(256, 10980 - 10752) = min(256, 228) = 228
```

---

## PHẦN 3 — GENERATOR PATTERN (Kỹ thuật Python quan trọng)

### 3.1 Vấn đề với cách return thông thường

Nếu bạn trả về **list** chứa tất cả chunk:
```python
def read_all_chunks(self, chunk_size=256):
    chunks = []
    for row_off in range(...):
        for col_off in range(...):
            chunks.append(ds.read(1, window=...))
    return chunks   # ← Vẫn nạp tất cả vào RAM! Mất ý nghĩa chunking
```

### 3.2 Generator — Trả từng phần tử một khi được yêu cầu

Generator dùng từ khóa `yield` thay vì `return`. Nó **không tính trước** — chỉ tính khi caller cần:

```python
# Hàm thông thường: tính hết rồi trả về
def squares_list(n):
    result = []
    for i in range(n):
        result.append(i * i)
    return result    # Trả về List → nạp hết vào RAM

# Generator: tính từng giá trị khi được yêu cầu
def squares_gen(n):
    for i in range(n):
        yield i * i  # Dừng lại đây, trả i*i cho caller, đợi caller gọi next()
```

```python
# Dùng generator:
for val in squares_gen(1000000):   # Chỉ lưu 1 số trong RAM tại mỗi thời điểm
    print(val)
```

### 3.3 Cơ chế hoạt động của Generator

```
Caller            Generator
  |                  |
  | → next()         |
  |                  | ← Thực thi đến yield
  |                  | → yield value
  | ← value          |
  |                  | ← Trạng thái đóng băng (frozen)
  |                  |
  | → next()         |
  |                  | ← Tiếp tục từ điểm yield cũ
  |                  | → yield value
  | ← value          |
```

Generator **lưu trạng thái** (local variables, vị trí thực thi) giữa các lần `yield` → đây là điểm khác biệt so với hàm thông thường.

### 3.4 Khi nào dùng Generator?

| Dùng List | Dùng Generator |
|---|---|
| Cần truy cập ngẫu nhiên (index) | Chỉ duyệt tuần tự 1 lần |
| Cần biết tổng số phần tử trước | Không biết trước số phần tử |
| Tập dữ liệu nhỏ, vừa RAM | Tập dữ liệu lớn, không vừa RAM |

→ **Chunked reading = use case hoàn hảo cho Generator**

---

## PHẦN 4 — `math.ceil` và PHÉP CHIA LẤY TRẦN

### 4.1 Tại sao cần `ceil`?

```
Ảnh rộng 10980 pixel, chunk 256 pixel:
10980 / 256 = 42.89...

Nếu dùng floor (//): 42 chunk → bỏ sót 228 pixel cuối!
Nếu dùng ceil:        43 chunk → đọc hết, chunk cuối nhỏ hơn (228 pixel)
```

### 4.2 Hai cách tính ceil trong Python

```python
import math

# Cách 1: math.ceil
n_chunks = math.ceil(10980 / 256)   # = 43

# Cách 2: Phép chia nguyên + 1 (không cần import)
n_chunks = (10980 + 256 - 1) // 256  # = 43  ← Trick phổ biến trong C/C++
```

---

## PHẦN 5 — INTERFACE HÀM CẦN VIẾT

### 5.1 Hàm `read_chunk()` — Generator trả về từng chunk

```python
def read_chunk(self, band_index: int = 1, chunk_size: int = 256):
    """
    Generator: đọc ảnh theo từng cửa sổ chunk_size × chunk_size.

    Tại mỗi lần yield, trả về tuple:
        (chunk_array, window, row_off, col_off)
    Trong đó:
        chunk_array : np.ndarray shape (h, w) — dữ liệu pixel của chunk
        window      : rasterio.windows.Window — mô tả vị trí chunk trong ảnh
        row_off     : int — hàng bắt đầu của chunk (pixel)
        col_off     : int — cột bắt đầu của chunk (pixel)

    Args:
        band_index : Band cần đọc (bắt đầu từ 1)
        chunk_size : Kích thước cạnh của chunk (mặc định 256 pixel)

    Usage:
        for chunk, window, row, col in wrapper.read_chunk(band_index=1):
            # xử lý chunk ở đây
            # chunk.shape = (actual_h, actual_w) — có thể nhỏ hơn chunk_size ở biên
            pass
    """
    # TODO: Dùng vòng lặp lồng nhau (row_off, col_off)
    # TODO: Tính actual_width và actual_height để xử lý chunk biên
    # TODO: Tạo Window object và gọi self.src.read(band_index, window=window)
    # TODO: yield (chunk, window, row_off, col_off)
    pass
```

### 5.2 Cách dùng sau khi implement xong

```python
wrapper = RasterWrapper("data/01_raw/B04_RED_test.tif")

total_pixels = 0
for chunk, window, row, col in wrapper.read_chunk(band_index=1, chunk_size=128):
    # chunk là numpy array shape (actual_h, actual_w)
    total_pixels += chunk.size
    print(f"Chunk tại ({row},{col}): shape={chunk.shape}, mean={chunk.mean():.1f}")

print(f"Tổng pixel đã xử lý: {total_pixels}")
# Kỳ vọng: total_pixels == 512 × 512 = 262144 (đủ toàn bộ ảnh)
```

---

## PHẦN 6 — KIỂM TRA KẾT QUẢ

### 6.1 Sanity Check quan trọng nhất

```python
# Tổng số pixel từ tất cả chunk phải bằng width × height
total = sum(chunk.size for chunk, _, _, _ in wrapper.read_chunk())
assert total == wrapper.width * wrapper.height, f"Thiếu pixel! {total} != {wrapper.width * wrapper.height}"
```

Nếu assert này pass → bạn không bỏ sót bất kỳ pixel nào.

### 6.2 Kiểm tra chunk biên (edge chunk)

```python
# Chunk cuối cùng phải có kích thước nhỏ hơn nếu không chia hết
# Với ảnh test 512×512, chunk_size=300:
# Chunk (0,0): shape = (300, 300)  ✓
# Chunk (0,1): shape = (300, 212)  ← 512 - 300 = 212
# Chunk (1,0): shape = (212, 300)
# Chunk (1,1): shape = (212, 212)
```

### 6.3 Test RAM usage (nâng cao, tùy chọn)

```bash
pip install memory-profiler
python -m memory_profiler scripts/verify_chunking.py
```

---

## 🎯 CHECKLIST — Sẵn sàng code Task 1.3 chưa?

- [ ] Tôi hiểu tại sao `.read()` toàn bộ nguy hiểm với ảnh 10980×10980.
- [ ] Tôi biết `Window(col_off, row_off, width, height)` hoạt động thế nào.
- [ ] Tôi hiểu `yield` khác `return` ở chỗ nào (frozen state).
- [ ] Tôi biết xử lý chunk biên bằng `min(chunk_size, total - offset)`.
- [ ] Tôi biết dùng `math.ceil` để tính số chunk cần thiết.
- [ ] Tôi biết kiểm tra bằng cách sum toàn bộ `.size` của các chunk.

---

## 📌 GHI NHỚ CỐT LÕI

| Khái niệm | Bản chất |
|---|---|
| `Window(c, r, w, h)` | Hình chữ nhật pixel: bắt đầu từ cột `c`, hàng `r`, rộng `w`, cao `h` |
| `ds.read(1, window=w)` | Chỉ nạp vùng pixel trong `w` vào RAM, không đọc toàn bộ |
| `yield` | Trả giá trị + đóng băng trạng thái, tiếp tục khi caller gọi `next()` |
| Chunk biên | `actual_w = min(chunk_size, total_width - col_off)` — luôn phải xử lý |
| Sanity check | `sum(chunk.size for ...)` phải bằng `width × height` |

---

*🔥 Đây là kỹ thuật streaming data — cùng nguyên lý với cách Python đọc file văn bản dòng từng dòng bằng `for line in file`. RAM dùng = 1 chunk, không phải toàn bộ file.*
