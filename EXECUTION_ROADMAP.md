# 🗺️ LỘ TRÌNH THỰC THI (EXECUTION ROADMAP)
**Dự án:** Satellite-based Rice Crop Monitoring (Bottom-up Approach)

> ⚠️ **Ràng buộc Tối Thượng**: KHÔNG sử dụng các thư viện ăn liền để tính toán lõi. Tự implement để học cách memory hoạt động. 
> Mục tiêu chính là tư duy cấu trúc dữ liệu, tối ưu hóa bộ nhớ và tốc độ xử lý I/O.

---

## 🗂️ GIAI ĐOẠN 1: TẠO DATAFLOW & QUẢN TRỊ I/O (File: `src/io/raster_wrapper.py`)
- [ ] **Task 1.1:** Khởi tạo class đọc ảnh raster (JP2 hoặc TIFF) từ thư mục `data/01_raw`.
- [ ] **Task 1.2:** Viết hàm trích xuất Metadata (Hệ tọa độ CRS, Transform matrix, kích thước ảnh gốc).
- [ ] **Task 1.3:** Viết hàm nạp dữ liệu rải rác (Chunking/Windowed Reading) thay vì nạp toàn bộ ảnh vào RAM. Cần đọc theo Block 256x256 hoặc 512x512 để tránh tràn RAM (OOM - Out Of Memory).

## 🧠 GIAI ĐOẠN 2: ĐỘNG CƠ CỐT LÕI - CORE ENGINE (File: `src/core/ndvi_engine.py`)
- [ ] **Task 2.1:** Khởi tạo hàm tính toán NDVI nhận vào Band 4 (RED) và Band 8 (NIR) ở dạng C-Array/Numpy array. `NDVI = (NIR - RED) / (NIR + RED)`
- [ ] **Task 2.2:** Xử lý rủi ro "Chia cho 0" (Vùng bóng râm hoặc nước) mà không dùng `for - if` lồng nhau. Sử dụng Bit-masking hoặc mảng điều kiện toán tử rẽ nhánh Vector của Numpy.
- [ ] **Task 2.3:** Tối ưu hóa tính toán (Strides manipulation, Vectorization) để giảm thời gian xử lý khi map qua mảng 10,980 x 10,980.

## 🎨 GIAI ĐOẠN 3: RENDERING & TRỰC QUAN HÓA (File: `src/viz/heatmap_generator.py`)
- [ ] **Task 3.1:** Viết hàm ánh xạ giá trị thập phân (Float từ -1.0 đến 1.0) sang thang màu (Color Mapping).
- [ ] **Task 3.2:** Sinh ma trận RGB đại diện cho hình ảnh đã được giả màu. Màu xanh = Lúa sinh trưởng tốt, Đỏ/Vàng = Mất mùa/Xâm nhập mặn.

## ⚙️ GIAI ĐOẠN 4: RÁP NỐI PIPELINE & CHẠY THỬ (File: `src/main.py`)
- [ ] **Task 4.1:** Ráp nối 3 module trên lại với luồng: Đọc dữ liệu IO -> Đưa vào Core Engine tính NDVI -> Chạy Viz sinh RGB -> Lưu kết quả về thư mục `data/03_output`.
- [ ] **Task 4.2:** Viết vòng lặp tuần tự đi qua từng chunk ảnh, tính toán, và ghi kết quả liên tục thay vì nạp lại toàn bộ.
- [ ] **Task 4.3:** Đo lường thời gian thực thi (Performance Profiling) và dung lượng RAM tiêu thụ bằng thư viện như `memory_profiler`.

---

## 🎤 MÔ PHỎNG PHỎNG VẤN - CÂU HỎI TECHNICAL GHI NHỚ
Đánh dấu `[x]` vào đây nếu bạn đã tự tin trả lời lưu loát trong buổi phỏng vấn (Mock Interview):

- [ ] **Q1 (Resource Management):** Tính toán dung lượng RAM tối đa bị chiếm dụng khi nạp toàn bộ một file ảnh 16-bit. Giải pháp cho hệ thống Docker bị giới hạn ở 256MB RAM?
- [ ] **Q2 (Exception Handling):** Bằng cách nào để tránh ngoại lệ "Divide by zero" mà không dùng vòng lặp `for-if` lồng nhau, giúp tránh "Branch Misprediction"?
- [ ] **Q3 (Memory Allocation):** Chi phí bộ nhớ trung gian phình to khi Casting từ `uint16` sang `float64`. Làm sao giảm thiểu phí tổn này?
- [ ] **Q4 (System I/O Bottleneck):** Tại sao việc dùng Multiprocessing không chia đều thời gian chạy theo tuyến tính (8 Cores không nhanh bằng 8 lần) cho Data-bound task?
- [ ] **Q5 (Data Locality/Cache miss):** Trình bày hiện tượng L1/L2 Cache Miss nếu vô tình đọc ma trận theo chuẩn `Column-major` ở một ngôn ngữ thiết kế theo `Row-major`?

---
*🔥 "Đừng sợ lỗi OOM (Out of Memory), đó là lúc bạn thực sự trở thành một Software Engineer."*
