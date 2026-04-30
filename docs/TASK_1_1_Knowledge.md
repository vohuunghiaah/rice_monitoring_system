# 📚 KIẾN THỨC NỀN TẢNG — TASK 1.1
> **Mục tiêu**: Hiểu đủ sâu để tự viết class đọc ảnh Raster từ `data/01_raw/`
> **File sẽ viết**: `src/io/raster_wrapper.py`

---

## PHẦN 1 — ẢNH VỆ TINH LÀ GÌ? (Raster Data)

### 1.1 Raster vs Vector
Trong GIS (Hệ thống thông tin địa lý) có 2 kiểu dữ liệu:
- **Vector**: Lưu theo điểm, đường, vùng (polygon). Ví dụ: ranh giới tỉnh thành.
- **Raster**: Lưu dưới dạng **lưới ô vuông (Grid)**, mỗi ô là một pixel có giá trị số. → Ảnh vệ tinh là Raster.

### 1.2 Cấu trúc dữ liệu của một ảnh Raster trong bộ nhớ
Hãy hình dung ảnh Raster là một **mảng 3 chiều (3D Array)**:

```
[Band(dải), Row(hàng), Column(cột)]  ←  NumPy shape
   4         10980          10980    ←  kích thước thực Sentinel-2
```

- **Band (Băng tần)**: Mỗi band là 1 "kênh" ánh sáng khác nhau (Đỏ, Xanh, Hồng ngoại...).
- **Row × Column**: Chiều cao × Chiều rộng ảnh tính bằng số pixel.
- **Giá trị mỗi pixel**: Là số nguyên **uint16** (-65535 → 65535), biểu diễn cường độ phản xạ ánh sáng.

### 1.3 Sentinel-2 — Band nào dùng để tính NDVI?
| Band | Tên | Bước sóng | Độ phân giải | Dùng để                   |
|------|-----|-----------|------------- |---------------------------|
| B04  | RED | 665 nm    | 10m/px       | Ánh sáng đỏ cây hấp thụ   |
| B08  | NIR | 842 nm    | 10m/px       | Hồng ngoại cây phản xạ    |

→ **Chỉ cần 2 band: B04 và B08** để tính NDVI.

### 1.4 Định dạng file
- **GeoTIFF (`.tif`)**: Định dạng phổ biến nhất, chứa cả dữ liệu pixel lẫn thông tin địa lý (CRS, Transform).
- **JPEG2000 (`.jp2`)**: Định dạng nén Sentinel-2 gốc tải về từ Copernicus Hub.

---

## PHẦN 2 — THÔNG TIN ĐỊA LÝ ĐÍNH KÈM (Geospatial Metadata)

Điều khác biệt lớn nhất của ảnh vệ tinh so với ảnh chụp thông thường là nó có **tọa độ thực địa** gắn liền. Khi bạn mở file, bạn không chỉ đọc pixel mà còn cần đọc 2 thứ quan trọng:

### 2.1 CRS — Hệ tọa độ tham chiếu (Coordinate Reference System)
- Mô tả cách **"chiếu"** bề mặt cầu Trái Đất lên mặt phẳng 2D.
- Sentinel-2 thường dùng **EPSG:32648** (UTM Zone 48N) cho khu vực Việt Nam.
- Được biểu diễn bằng chuỗi **WKT** hoặc mã **EPSG**.

```
Ví dụ: "EPSG:32648" → UTM Zone 48N → phù hợp Đồng bằng sông Cửu Long
```

### 2.2 Affine Transform Matrix — Ma trận biến đổi
Đây là **ma trận 3×3** ánh xạ từ **tọa độ pixel (col, row)** sang **tọa độ thực địa (longitude, latitude) - (kinh độ, vĩ độ)**.

```
| x_real |   | a  b  c |   | col |
| y_real | = | d  e  f | × | row |
|   1    |   | 0  0  1 |   |  1  |
```

Trong đó:
- `(c, f)`: Tọa độ thực địa của góc trên-trái của ảnh (origin).
- `a`: Kích thước pixel theo chiều X (thường = +10.0 mét với Sentinel-2 10m).
- `e`: Kích thước pixel theo chiều Y (thường = **-10.0** vì trục Y đảo ngược: hàng 0 ở **trên**).
- `b, d`: Thường = 0 nếu ảnh không bị xoay.

**Tại sao cần matrix này?** Để sau khi tính NDVI xong, bạn có thể ghi kết quả ra file mới vẫn giữ nguyên tọa độ thực địa.

---

## PHẦN 3 — THƯ VIỆN `rasterio` — CẦU NỐI PYTHON ↔ FILE ẢNH

### 3.1 Rasterio là gì?
`rasterio` là thư viện Python wrapper của **GDAL** (Geospatial Data Abstraction Library — viết bằng C++). Nó giúp Python đọc/ghi các định dạng GeoTIFF, JP2, HDF5... mà không cần tự parse binary file.

### 3.2 Khái niệm cốt lõi: Dataset Object
Khi mở file với rasterio, bạn nhận về một **Dataset Object** — tương tự như `file handle` khi dùng `open()` thông thường.

```python
import rasterio

# Mở file — chưa đọc dữ liệu vào RAM
dataset = rasterio.open("data/01_raw/T48PXS_B04.jp2")

# Thông tin metadata
dataset.count      # Số band (thường = 1 cho từng file jp2 của Sentinel-2)
dataset.width      # Số cột (pixel)
dataset.height     # Số hàng (pixel)
dataset.dtypes     # Kiểu dữ liệu của mỗi band, ví dụ ('uint16',)
dataset.crs        # Hệ tọa độ CRS
dataset.transform  # Affine Transform Matrix

# ĐỌC toàn bộ band 1 vào RAM dưới dạng NumPy array
data = dataset.read(1)  # shape: (height, width)

dataset.close()
```

> ⚠️ **Vấn đề**: `dataset.read(1)` nạp **toàn bộ** ảnh vào RAM. Với ảnh 10980×10980 uint16 = ~228MB chỉ cho 1 band. Đây là lý do Task 1.3 sẽ học Chunking.

### 3.3 Context Manager — Pattern đúng chuẩn (Dùng `with`)
Python cung cấp **Context Manager** để đảm bảo file luôn được đóng đúng cách, dù có lỗi xảy ra hay không:

```python
# Pattern chuẩn — file tự đóng khi thoát khỏi block `with`
with rasterio.open("path/to/file.tif") as dataset:
    meta = dataset.meta      # Đọc metadata
    data = dataset.read(1)   # Đọc band 1
# dataset đã tự .close() ở đây
```

Cơ chế: Python gọi `__enter__()` khi vào `with`, và gọi `__exit__()` khi ra — dù thành công hay exception.

---

## PHẦN 4 — CLASS TRONG PYTHON (OOP CƠ BẢN)

Task 1.1 yêu cầu bạn viết **class**. Đây là cấu trúc bạn cần nắm:

### 4.1 Cấu trúc class cơ bản
```python
class TenClass:
    def __init__(self, tham_so):   # Constructor — chạy khi tạo object
        self.bien_noi_tai = tham_so  # Lưu trạng thái bên trong object

    def ten_phuong_thuc(self):     # Method — hành vi của object
        return self.bien_noi_tai
```

### 4.2 `self` là gì?
`self` là tham chiếu đến **chính object đó**. Mọi attribute (biến) và method (hàm) của object đều truy cập qua `self`.

```python
obj = TenClass("hello")
obj.ten_phuong_thuc()   # → "hello"
```

### 4.3 Thiết kế class cho RasterWrapper
Bạn cần class có khả năng:
1. Nhận đường dẫn file ảnh.
2. Mở file và đọc metadata.
3. Đóng file khi dùng xong.

Gợi ý **interface** (chưa viết logic — đó là việc của bạn):

```python
class RasterWrapper:
    def __init__(self, file_path: str):
        # TODO: Lưu đường dẫn, mở file, đọc metadata
        pass

    def get_metadata(self) -> dict:
        # TODO: Trả về dict chứa: width, height, crs, transform, dtype, count
        pass

    def read_band(self, band_index: int):
        # TODO: Đọc 1 band, trả về numpy array shape (height, width)
        pass

    def close(self):
        # TODO: Đóng file dataset
        pass
```

---

## PHẦN 5 — QUẢN LÝ BỘ NHỚ CƠ BẢN (Tại sao phải cẩn thận?)

### 5.1 Tính toán RAM tiêu thụ
Hãy tự tính trước khi code:

```
1 pixel Sentinel-2  = uint16  = 2 bytes
1 band B04          = 10980 × 10980 × 2 bytes
                    = 120,692,400 bytes
                    ≈ 115 MB  (cho 1 band)

Cả 4 band (B02,B03,B04,B08) = ~460 MB
```

→ Nếu load cả 4 band cùng lúc, đã chiếm gần **500MB RAM** chỉ để đọc dữ liệu thô.

### 5.2 Nguyên tắc "Đọc Lazy" (Lazy Loading)
`rasterio.open()` **không đọc pixel** ngay — nó chỉ mở file handle và đọc header.
Dữ liệu thực sự chỉ được nạp vào RAM khi bạn gọi `.read()`.

→ Đây là **Lazy Loading**: chỉ tải khi cần.

### 5.3 File Handle — Tài nguyên phải giải phóng
File handle là tài nguyên hệ điều hành (OS resource). Nếu bạn mở 1000 file mà không đóng → hệ thống báo lỗi **"Too many open files"**.

Luôn đảm bảo `dataset.close()` được gọi — hoặc dùng `with` block.

---

## PHẦN 6 — CÀI ĐẶT MÔI TRƯỜNG

### 6.1 Cài thư viện cần thiết
```bash
pip install rasterio numpy
```

> **Lưu ý Windows**: `rasterio` trên Windows đôi khi cần cài qua `conda` để tránh lỗi GDAL:
> ```bash
> conda install -c conda-forge rasterio
> ```

### 6.2 Kiểm tra cài đặt thành công
```python
import rasterio
print(rasterio.__version__)  # In ra phiên bản, ví dụ: 1.3.9
```

### 6.3 Tải dữ liệu Sentinel-2 thử nghiệm
Truy cập: **https://browser.dataspace.copernicus.eu/**
- Tạo tài khoản miễn phí → tìm khu vực ĐBSCL → tải file Level-2A → đặt vào `data/01_raw/`

---

## 🎯 CHECKLIST — Bạn đã hiểu đủ để bắt tay code Task 1.1 chưa?

- [x] Tôi hiểu ảnh raster là mảng 3D `[Band, Row, Col]`.
- [ ] Tôi biết Sentinel-2 lưu định dạng JP2, mỗi file là 1 band.
- [x] Tôi biết `rasterio.open()` chưa đọc pixel ngay.
- [x] Tôi hiểu `dataset.transform` là ma trận Affine.
- [ ] Tôi biết viết class Python với `__init__`, `self`, và các method.
- [ ] Tôi đã tính được: 1 band Sentinel-2 ≈ 115MB RAM.
- [x] Tôi biết phải `close()` file sau khi dùng xong (hoặc dùng `with`).

---

## 📌 GHI NHỚ CỐT LÕI (1 câu cho mỗi khái niệm)

| Khái niệm            | Bản chất                                                          |
|----------------------|-------------------------------------------------------------------|
| Raster Image         | Mảng 3D số nguyên `[Band, H, W]` lưu cường độ phản xạ ánh sáng    |
| Band                 | 1 kênh ảnh = 1 mảng 2D. Sentinel-2 có 13 bands.                   |
| CRS                  | "Ngôn ngữ tọa độ" — cho biết pixel ứng với kinh độ/vĩ độ nào      |
| Affine Transform     | Ma trận 3×3 chuyển đổi (col, row) → (x_real, y_real)              |
| rasterio.open()      | Chỉ mở file handle + đọc header, CHƯA nạp pixel vào RAM           |
| `with` block         | Đảm bảo file.close() luôn được gọi — tránh rò rỉ tài nguyên       |
| uint16               | Kiểu số nguyên 16-bit (0→65535), mỗi pixel chiếm 2 bytes          |

---

*🔥 Sau khi đọc xong file này, hãy thử tự viết class `RasterWrapper` vào `src/io/raster_wrapper.py`. Gặp lỗi hay bí chỗ nào hãy hỏi tôi để tôi phân tích nguyên lý sâu hơn!*
