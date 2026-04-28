"""
preview_bands.py
================
Script xem trước (preview) 2 file GeoTIFF Band 4 và Band 8.

TẠI SAO CẦN SCRIPT NÀY?
  File .tif của chúng ta lưu kiểu uint16 (0 → 65535).
  Trình xem ảnh thông thường (Windows Photo, VS Code) chỉ hiểu uint8 (0 → 255).
  → Khi mở thẳng file .tif → ảnh bị đen vì viewer đọc sai dải giá trị.

SCRIPT NÀY LÀM GÌ?
  1. Đọc mảng uint16 từ file .tif
  2. Normalize về dải 0→255 (uint8) — kỹ thuật gọi là "Linear Stretch"
  3. Vẽ ảnh và lưu ra file .png trong data/03_output/ để bạn mở bình thường

Cách chạy:
  cd c:\\VSCode\\rice_monitoring_system
  python scripts/preview_bands.py
"""

import numpy as np
import rasterio
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import os


def linear_stretch(arr: np.ndarray, low_pct: float = 2.0, high_pct: float = 98.0) -> np.ndarray:
    """
    Normalize mảng uint16 về dải 0→255 (uint8) dùng kỹ thuật Percentile Stretch.

    Tại sao dùng percentile thay vì min/max?
      - Nếu dùng min/max: 1 pixel nhiễu cực sáng làm toàn bộ ảnh tối đen.
      - Dùng percentile 2%→98%: Bỏ qua 2% giá trị thấp nhất và 2% cao nhất,
        tập trung stretch vào vùng giá trị thực sự của ảnh → kết quả tự nhiên hơn.

    Đây là kỹ thuật chuẩn trong Remote Sensing gọi là "Linear Contrast Enhancement".
    """
    lo = np.percentile(arr, low_pct)   # Giá trị ở mức 2% từ dưới
    hi = np.percentile(arr, high_pct)  # Giá trị ở mức 98% từ dưới

    # Clip về đúng dải [lo, hi], rồi scale tuyến tính về [0, 255]
    stretched = np.clip(arr, lo, hi)
    stretched = (stretched - lo) / (hi - lo) * 255.0
    return stretched.astype(np.uint8)


def load_band(file_path: str):
    """Đọc band 1 từ file GeoTIFF, trả về (array_uint16, metadata_dict)."""
    with rasterio.open(file_path) as ds:
        arr = ds.read(1)   # Đọc band index 1
        meta = {
            "width": ds.width,
            "height": ds.height,
            "dtype": str(ds.dtypes[0]),
            "crs": str(ds.crs),
            "pixel_size_m": abs(ds.transform.a),  # Kích thước pixel theo mét
        }
    return arr, meta


def main():
    # --- Đường dẫn ---
    base = os.path.join(os.path.dirname(__file__), "..")
    path_red = os.path.join(base, "data", "01_raw", "B04_RED_test.tif")
    path_nir = os.path.join(base, "data", "01_raw", "B08_NIR_test.tif")
    output_dir = os.path.join(base, "data", "03_output")
    os.makedirs(output_dir, exist_ok=True)

    # --- Kiểm tra file tồn tại ---
    for p in [path_red, path_nir]:
        if not os.path.exists(p):
            print(f"❌ Không tìm thấy: {p}")
            print("   → Chạy trước: python scripts/generate_test_data.py")
            return

    # --- Đọc dữ liệu ---
    arr_red, meta_red = load_band(path_red)
    arr_nir, meta_nir = load_band(path_nir)

    print("📊 THÔNG TIN FILE GỐC (uint16 — trước khi normalize):")
    print(f"   Band RED → min={arr_red.min()}, max={arr_red.max()}, mean={arr_red.mean():.1f}")
    print(f"   Band NIR → min={arr_nir.min()}, max={arr_nir.max()}, mean={arr_nir.mean():.1f}")
    print(f"   Shape    → {arr_red.shape}  |  dtype: {meta_red['dtype']}")
    print(f"   CRS      → {meta_red['crs']}")
    print(f"   Pixel    → {meta_red['pixel_size_m']}m x {meta_red['pixel_size_m']}m")
    print()

    # --- Normalize về uint8 để hiển thị ---
    red_display = linear_stretch(arr_red)
    nir_display = linear_stretch(arr_nir)

    print("🎨 THÔNG TIN SAU KHI NORMALIZE (uint8 — dùng để hiển thị):")
    print(f"   Band RED → min={red_display.min()}, max={red_display.max()}")
    print(f"   Band NIR → min={nir_display.min()}, max={nir_display.max()}")
    print()

    # --- Vẽ hình ---
    fig = plt.figure(figsize=(16, 10), facecolor="#1a1a2e")
    fig.suptitle(
        "Sentinel-2 Band Preview — Khu vực ĐBSCL (Giả lập)",
        fontsize=16, fontweight="bold", color="white", y=0.98
    )

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

    # Panel 1: Band RED (grayscale)
    ax1 = fig.add_subplot(gs[0, 0])
    im1 = ax1.imshow(red_display, cmap="Reds_r", vmin=0, vmax=255)
    ax1.set_title("Band 4 (RED) — Grayscale\nuint16 → normalized uint8", color="white", fontsize=10)
    ax1.axis("off")
    plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04).ax.yaxis.set_tick_params(color="white")

    # Panel 2: Band NIR (grayscale)
    ax2 = fig.add_subplot(gs[0, 1])
    im2 = ax2.imshow(nir_display, cmap="Greens_r", vmin=0, vmax=255)
    ax2.set_title("Band 8 (NIR) — Grayscale\nuint16 → normalized uint8", color="white", fontsize=10)
    ax2.axis("off")
    plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)

    # Panel 3: Giải thích vùng dữ liệu
    ax3 = fig.add_subplot(gs[0, 2])
    region_map = np.zeros((512, 512, 3), dtype=np.uint8)
    region_map[:, 0:171]   = [34, 139, 34]    # Xanh lá = lúa khỏe
    region_map[:, 171:342] = [210, 180, 140]  # Vàng nâu = xâm nhập mặn
    region_map[:, 342:]    = [65, 105, 225]   # Xanh dương = mặt nước
    ax3.imshow(region_map)
    ax3.set_title("Bản đồ vùng dữ liệu\n(3 vùng giả lập)", color="white", fontsize=10)
    ax3.set_xlabel("← Lúa khỏe | Mặn | Nước →", color="#aaaaaa", fontsize=8)
    ax3.axis("off")

    # Panel 4: Histogram Band RED
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.hist(arr_red.flatten(), bins=80, color="#e74c3c", alpha=0.8, edgecolor="none")
    ax4.set_title("Histogram: Band RED (uint16)\nPhân phối giá trị pixel", color="white", fontsize=10)
    ax4.set_xlabel("Giá trị pixel (uint16)", color="#aaaaaa")
    ax4.set_ylabel("Số pixel", color="#aaaaaa")
    ax4.tick_params(colors="#aaaaaa")
    ax4.set_facecolor("#0f3460")
    ax4.spines[:].set_color("#444")

    # Panel 5: Histogram Band NIR
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.hist(arr_nir.flatten(), bins=80, color="#2ecc71", alpha=0.8, edgecolor="none")
    ax5.set_title("Histogram: Band NIR (uint16)\nPhân phối giá trị pixel", color="white", fontsize=10)
    ax5.set_xlabel("Giá trị pixel (uint16)", color="#aaaaaa")
    ax5.set_ylabel("Số pixel", color="#aaaaaa")
    ax5.tick_params(colors="#aaaaaa")
    ax5.set_facecolor("#0f3460")
    ax5.spines[:].set_color("#444")

    # Panel 6: Scatter plot NIR vs RED (chỉ dùng 5000 pixel ngẫu nhiên)
    ax6 = fig.add_subplot(gs[1, 2])
    rng = np.random.default_rng(seed=0)
    idx = rng.choice(512 * 512, size=5000, replace=False)
    colors_scatter = []
    for i in idx:
        col = i % 512
        if col < 171:
            colors_scatter.append("#2ecc71")   # Lúa khỏe → xanh
        elif col < 342:
            colors_scatter.append("#e67e22")   # Mặn → cam
        else:
            colors_scatter.append("#3498db")   # Nước → xanh dương
    ax6.scatter(
        arr_red.flatten()[idx], arr_nir.flatten()[idx],
        c=colors_scatter, s=2, alpha=0.5
    )
    ax6.set_title("NIR vs RED Scatter\n(5000 pixel ngẫu nhiên)", color="white", fontsize=10)
    ax6.set_xlabel("Band RED (uint16)", color="#aaaaaa")
    ax6.set_ylabel("Band NIR (uint16)", color="#aaaaaa")
    ax6.tick_params(colors="#aaaaaa")
    ax6.set_facecolor("#0f3460")
    ax6.spines[:].set_color("#444")
    # Chú thích màu
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#2ecc71", label="Lúa khỏe"),
        Patch(facecolor="#e67e22", label="Xâm nhập mặn"),
        Patch(facecolor="#3498db", label="Mặt nước"),
    ]
    ax6.legend(handles=legend_elements, fontsize=8,
               facecolor="#1a1a2e", labelcolor="white", loc="upper right")

    # Tô màu nền tất cả axes
    for ax in [ax1, ax2, ax3, ax4, ax5, ax6]:
        ax.set_facecolor("#0f3460")

    # --- Lưu file ---
    output_path = os.path.join(output_dir, "band_preview.png")
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor="#1a1a2e", edgecolor="none")
    plt.show()

    print(f"✅ Đã lưu preview tại: {output_path}")
    print()
    print("💡 Giải thích kỹ thuật — tại sao file .tif bị đen khi mở thẳng:")
    print("   File lưu kiểu uint16 (0→65535). Viewer ảnh thông thường chỉ")
    print("   hiểu uint8 (0→255). Giá trị 3500 bị 'tối' vì viewer scale sai.")
    print("   Script này dùng 'Linear Stretch' (percentile 2%→98%) để normalize")
    print("   về đúng dải uint8 → ảnh hiển thị đúng màu sắc.")


if __name__ == "__main__":
    main()
