import pprint
from src.io.raster_wrapper import RasterWrapper

def main():
    file_path = "./data/01_raw/B04_RED.jp2"
    print("[INFO] Khởi chạy kiểm tra I/O Pipeline...\n")

    with RasterWrapper(file_path) as band4:
        # Căn giữa tiêu đề với tổng chiều dài 60 ký tự
        print(" THÔNG SỐ KỸ THUẬT CỐT LÕI (METADATA) ".center(60, "*"))

        # Sử dụng ký pháp :<25 để căn lề trái 25 ký tự, giúp dấu ':' thẳng hàng
        print(f"{'Kích thước (W x H)':<25}: {band4.width} x {band4.height} pixels")
        print(f"{'Kiểu dữ liệu':<25}: {band4.dtypes}")
        print(f"{'Hệ tọa độ (CRS)':<25}: {band4.crs}")
        print(f"{'Số lượng Band':<25}: {band4.count}")

        print("\n" + "-"*60)
        print(" MA TRẬN ÁNH XẠ TỌA ĐỘ (AFFINE TRANSFORM) ".center(60))
        print("-"*60)
        # Bản thân object Affine đã có hàm __str__ định dạng ma trận 3x3
        print(band4.transform)

        print("\n" + "-"*60)
        print(" RAW METADATA DICTIONARY ".center(60))
        print("-"*60)
        
        # Sử dụng pprint thay cho print để in từ điển (dict)
        # indent=4: thụt lề 4 space cho mỗi cấp
        # sort_dicts=False: Giữ nguyên thứ tự key gốc của rasterio
        pprint.pprint(band4.meta, indent=4, sort_dicts=False)
        
        print("\n" + "="*60)

if __name__ == "__main__":
    main()