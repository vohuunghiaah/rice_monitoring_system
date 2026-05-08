from manim import *
import numpy as np

# =====================================================================
# CẤU HÌNH 1080p @ 60fps
# Chạy: manim -qh --fps 60 visualization.py FullSpatialPipeline
# =====================================================================
config.pixel_width = 1920
config.pixel_height = 1080
config.frame_rate = 60
config.frame_width = 16      # tỉ lệ 16:9
config.frame_height = 9

class FullSpatialPipeline(ThreeDScene):
    def construct(self):
        # =============================================================
        # BẢNG MÀU
        # =============================================================
        C_RAM   = BLUE_D
        C_LOGIC = TEAL_D
        C_PHYS  = ORANGE
        C_3D    = RED_E
        C_NDVI  = GREEN_D
        C_HEAT  = YELLOW
        GREEN_YELLOW = "#ADFF2F"
        FNT     = "sans-serif"

        W = 4   # width of logical grid

        # =============================================================
        # GIAI ĐOẠN 1 — Bộ nhớ vật lý: Mảng 1D trên RAM
        # =============================================================
        t1 = Text("Giai đoạn 1: Mảng 1D tuần tự trên RAM",
                   font_size=36, font=FNT).to_edge(UP)
        self.play(Write(t1))

        ram = VGroup(*[
            Square(side_length=0.55, fill_opacity=0.7, color=C_RAM)
            for _ in range(16)
        ]).arrange(RIGHT, buff=0.08).move_to(ORIGIN)

        idx_labels = VGroup(*[
            Text(str(i), font_size=18).move_to(ram[i])
            for i in range(16)
        ])
        self.play(FadeIn(ram, shift=UP), Write(idx_labels))

        ptr = Arrow(UP * 0.8, ORIGIN, color=YELLOW).next_to(ram[6], UP, buff=0.1)
        self.play(FadeIn(ptr))
        self.play(ram[6].animate.set_color(YELLOW).set_fill(opacity=0.9))
        self.wait(0.8)

        # =============================================================
        # GIAI ĐOẠN 2 — Lưới logic 2D (Pointer Arithmetic)
        # =============================================================
        t2 = Text("Giai đoạn 2: Tính toán Lưới 2D (Logical Grid)",
                   font_size=36, font=FNT).to_edge(UP)

        formula = MathTex(
            r"col = i \bmod W", r"\quad",
            r"row = \lfloor i / W \rfloor",
            font_size=40
        ).next_to(t2, DOWN, buff=0.3)

        self.play(Transform(t1, t2), FadeOut(ptr), Write(formula))
        self.play(ram.animate.set_color(C_LOGIC))

        grid = VGroup()
        for r in range(W):
            grid.add(VGroup(*ram[r * W:(r + 1) * W]))

        self.play(
            grid.animate.arrange_in_grid(rows=W, cols=W, buff=0.08)
                        .move_to(DOWN * 0.5),
            idx_labels.animate.set_opacity(0)
        )
        self.wait(1)

        # =============================================================
        # GIAI ĐOẠN 3 — Ma trận Affine → Tọa độ thực địa (mét)
        # =============================================================
        t3 = Text("Giai đoạn 3: Ma trận Affine → Tọa độ Thực địa (Mét)",
                   font_size=34, font=FNT).to_edge(UP)

        mat_tex = MathTex(
            r"\begin{bmatrix} X \\ Y \\ 1 \end{bmatrix} =",
            r"\begin{bmatrix} a & b & c \\ d & e & f \\ 0 & 0 & 1 \end{bmatrix}",
            r"\begin{bmatrix} col \\ row \\ 1 \end{bmatrix}",
            font_size=36
        ).next_to(t3, DOWN, buff=0.25)

        self.play(Transform(t1, t3), FadeOut(formula), Write(mat_tex))

        demo_i = 6
        demo_col = demo_i % W   # = 2
        demo_row = demo_i // W  # = 1

        a, b, c_val = 1.0, 0.0, 0.5
        d, e, f_val = 0.0, -1.0, 3.0
        X_val = a * demo_col + b * demo_row + c_val  # 2.5
        Y_val = d * demo_col + e * demo_row + f_val  # 2.0

        step_tex = MathTex(
            r"i=6 \;\Rightarrow\; col=2,\; row=1",
            font_size=30
        ).to_corner(DR, buff=0.8)

        # Gộp thành 1 chuỗi raw duy nhất để tránh lỗi biên dịch mảng mobject
        result_tex = MathTex(
            r"\vec{P} = \begin{bmatrix} X \\ Y \end{bmatrix} = \begin{bmatrix} 2.5 \\ 2.0 \end{bmatrix} \text{ (m)}",
            font_size=30
        )
        result_tex.next_to(step_tex, UP, buff=0.4).align_to(step_tex, RIGHT)

        self.play(Write(step_tex))
        self.play(Write(result_tex))

        # Sử dụng axis_config chuẩn hóa thay vì tips=True để tương thích mọi phiên bản
        ax3 = Axes(
            x_range=[0, 5, 1], y_range=[0, 4, 1],
            x_length=5, y_length=3.5,
            axis_config={"include_numbers": True, "font_size": 20, "include_tip": True}
        ).move_to(DOWN * 0.3 + LEFT * 3.5) 
        
        ax_labels = ax3.get_axis_labels(
            x_label=MathTex("X", font_size=28),
            y_label=MathTex("Y", font_size=28)
        )

        self.play(grid.animate.set_opacity(0.15), run_time=0.5)
        self.play(Create(ax3), Write(ax_labels))

        origin_pt = ax3.c2p(0, 0)
        target_pt = ax3.c2p(X_val, Y_val)
        
        vec_arrow = Arrow(
            origin_pt, target_pt,
            color=C_PHYS, buff=0, stroke_width=5
        )
        vec_dot = Dot(target_pt, color=YELLOW, radius=0.1)
        vec_label = MathTex(r"\vec{P}(2.5,\,2.0)", font_size=26, color=YELLOW
                            ).next_to(vec_dot, UR, buff=0.15)

        self.play(GrowArrow(vec_arrow), FadeIn(vec_dot), Write(vec_label))
        self.wait(1.5)

        # =============================================================
        # GIAI ĐOẠN 4 — Reprojection: UTM → WGS84 Sphere
        # =============================================================
        t4 = Text("Giai đoạn 4: Chiếu ngược từ 2D UTM lên Cầu WGS84",
                   font_size=34, font=FNT).to_edge(UP)
        
        # Gọi thẳng hàm FadeOut từng thành phần để tránh lỗi VGroup
        self.play(
            Transform(t1, t4),
            FadeOut(mat_tex), FadeOut(grid), FadeOut(step_tex), FadeOut(result_tex), FadeOut(ax_labels),
            run_time=1
        )

        step1_txt = Text("1. Giải mã tọa độ (X, Y):", 
                         font_size=20, font=FNT, color=TEAL)
        step1_sub = Text("→ λ = 106.7° (Kinh độ), φ = 10.8° (Vĩ độ)", 
                         font_size=20, font=FNT, color=TEAL)
        step1_group = VGroup(step1_txt, step1_sub).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        
        step2_txt = Text("2. Hệ tọa độ cầu 3D (Bán kính R = 2.2):", 
                         font_size=20, font=FNT, color=YELLOW)
        
        formula_eq = MathTex(
            r"x &= R \cdot \cos(\phi) \cdot \cos(\lambda) \\"
            r"y &= R \cdot \cos(\phi) \cdot \sin(\lambda) \\"
            r"z &= R \cdot \sin(\phi)",
            font_size=26
        )

        value_eq = MathTex(
            r"x &= 2.2 \cdot \cos(10.8^\circ) \cdot \cos(106.7^\circ) &\approx -0.62 \\"
            r"y &= 2.2 \cdot \cos(10.8^\circ) \cdot \sin(106.7^\circ) &\approx 2.07 \\"
            r"z &= 2.2 \cdot \sin(10.8^\circ) &\approx 0.41",
            font_size=26
        )

        step2_group = VGroup(step2_txt, formula_eq).arrange(DOWN, aligned_edge=LEFT, buff=0.2)
        instructions = VGroup(step1_group, step2_group).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        
        instructions.move_to(RIGHT * 4 + UP * 0.5) 
        value_eq.move_to(formula_eq, aligned_edge=LEFT)

        self.play(Write(step1_group))
        self.wait(0.5)
        self.play(Write(step2_txt), Write(formula_eq))
        self.wait(1.5)

        self.play(Transform(formula_eq, value_eq), run_time=1.5)
        self.wait(2.5)
        
        self.play(FadeOut(instructions), FadeOut(formula_eq), run_time=0.8)

        self.move_camera(phi=60 * DEGREES, theta=-45 * DEGREES, run_time=1.5)

        axes_3d = ThreeDAxes(
            x_range=[-3, 3], y_range=[-3, 3], z_range=[-3, 3],
            x_length=6, y_length=6, z_length=6
        )
        sphere = Sphere(
            radius=2.2, resolution=(32, 32)
        ).set_color(BLUE_E).set_opacity(0.35)

        self.play(Create(axes_3d), FadeIn(sphere), FadeOut(ax3), FadeOut(vec_label))

        lat_rad = 10.8 * DEGREES
        lon_rad = 106.7 * DEGREES
        r = 2.2
        target_3d_pos = [
            r * np.cos(lat_rad) * np.cos(lon_rad),
            r * np.cos(lat_rad) * np.sin(lon_rad),
            r * np.sin(lat_rad)
        ]
        
        dot_3d = Dot3D(target_3d_pos, color=YELLOW, radius=0.1)
        vector_line = Line(ORIGIN, target_3d_pos, color=YELLOW_D, stroke_width=2)

        self.play(
            ReplacementTransform(vec_arrow, vector_line),
            ReplacementTransform(vec_dot, dot_3d),
            run_time=2.5, rate_func=smooth
        )
        
        pts3d = VGroup()
        np.random.seed(42)
        for k in range(15):
            lat_a = lat_rad + (np.random.rand() - 0.5) * 0.5
            lon_a = lon_rad + (np.random.rand() - 0.5) * 0.5
            x = r * np.cos(lat_a) * np.cos(lon_a)
            y = r * np.cos(lat_a) * np.sin(lon_a)
            z = r * np.sin(lat_a)
            pts3d.add(Dot3D([x, y, z], color=C_3D, radius=0.06))

        self.play(FadeIn(pts3d), run_time=1)

        coord_label = Text(
            "lon=106.7E, lat=10.8N", font_size=22, color=YELLOW, font=FNT
        ).to_edge(DOWN, buff=0.5)
        coord_label.set_opacity(0)
        self.add_fixed_in_frame_mobjects(coord_label)
        
        self.play(coord_label.animate.set_opacity(1))

        self.move_camera(theta=15 * DEGREES, run_time=3, rate_func=smooth)
        self.wait(1.5)

        self.play(
            FadeOut(pts3d), FadeOut(dot_3d), FadeOut(vector_line), FadeOut(axes_3d), 
            FadeOut(sphere), FadeOut(coord_label),
            run_time=1
        )
        self.move_camera(phi=0, theta=-PI / 2, run_time=1)

        # =============================================================
        # GIAI ĐOẠN 5 — Xử lý xung đột độ phân giải giữa các Band
        # =============================================================
        t5 = Text("Giai đoạn 5: Coregistration & Resampling qua Affine",
                   font_size=34, font=FNT).to_edge(UP)
        self.play(Transform(t1, t5))

        band_10m = VGroup()
        for name, clr in [("B2\nBlue", BLUE), ("B3\nGreen", GREEN),
                           ("B4\nRed", RED), ("B8\nNIR", MAROON)]:
            box = VGroup(
                Square(side_length=1.0, fill_opacity=0.7, color=clr)
                    .set_stroke(WHITE, 2),
                Text(name, font_size=14, font=FNT, color=WHITE)
            )
            box[1].move_to(box[0])
            band_10m.add(box)
        band_10m.arrange(RIGHT, buff=0.15)

        band_20m = VGroup()
        for name, clr in [("B5\nRE1", GOLD), ("B6\nRE2", GOLD_D),
                           ("B8A\nNIR2", MAROON_D), ("B11\nSWIR", TEAL)]:
            box = VGroup(
                Square(side_length=0.5, fill_opacity=0.6, color=clr)
                    .set_stroke(WHITE, 1.5),
                Text(name, font_size=12, font=FNT, color=WHITE)
            )
            box[1].move_to(box[0])
            band_20m.add(box)
        band_20m.arrange(RIGHT, buff=0.1)

        lbl_10 = Text("10 m/px", font_size=20, font=FNT, color=GREEN_A)
        lbl_20 = Text("20 m/px", font_size=20, font=FNT, color=GOLD_A)

        col_10 = VGroup(lbl_10, band_10m).arrange(DOWN, buff=0.2)
        col_20 = VGroup(lbl_20, band_20m).arrange(DOWN, buff=0.2)

        bands_all = VGroup(col_10, col_20).arrange(DOWN, buff=0.5).move_to(DOWN * 0.5)
        self.play(FadeIn(bands_all), run_time=1.2)
        self.wait(1)

        conflict_r1 = SurroundingRectangle(
            band_10m[2], color=RED_A, buff=0.08, stroke_width=3
        )
        conflict_r2 = SurroundingRectangle(
            band_20m[2], color=RED_A, buff=0.08, stroke_width=3
        )
        conflict_text = Text("B4 (10m) + B8A (20m) → Bất đồng bộ Pixel",
                             font_size=24, font=FNT, color=RED_A
                             ).next_to(bands_all, DOWN, buff=0.4)
        self.play(
            Create(conflict_r1), Create(conflict_r2), Write(conflict_text)
        )
        self.wait(1.5)

        self.play(FadeOut(conflict_text), FadeOut(conflict_r1), FadeOut(conflict_r2), FadeOut(bands_all))

        affine_eq_title = Text("Bước 1: Tìm pixel đích qua ma trận Affine",
                               font_size=22, font=FNT, color=TEAL).next_to(t5, DOWN, buff=0.3)
        
        affine_eq = MathTex(
            r"Pixel_{20m} = \mathbf{A}_{20m}^{-1} \cdot \mathbf{A}_{10m} \cdot Pixel_{10m}",
            font_size=36, color=WHITE
        ).next_to(affine_eq_title, DOWN, buff=0.2)
        
        self.play(Write(affine_eq_title), Write(affine_eq))
        self.wait(1.5)

        resample_title = Text("Bước 2: Nội suy giá trị (Bilinear Interpolation)",
                              font_size=22, font=FNT, color=YELLOW
                              ).next_to(affine_eq, DOWN, buff=0.4)
        self.play(Write(resample_title))

        grid_20 = VGroup(*[
            Square(side_length=0.7, fill_opacity=0.6, color=MAROON_D)
            .set_stroke(WHITE, 1.5)
            for _ in range(4)
        ]).arrange_in_grid(rows=2, cols=2, buff=0.05).move_to(LEFT * 3.5 + DOWN * 1.8)

        grid_20_lbl = Text("B8A (20m)\n2x2 px", font_size=16, font=FNT
                           ).next_to(grid_20, DOWN, buff=0.15)

        grid_10 = VGroup(*[
            Square(side_length=0.35, fill_opacity=0.6, color=MAROON)
            .set_stroke(WHITE, 1)
            for _ in range(16)
        ]).arrange_in_grid(rows=4, cols=4, buff=0.03).move_to(RIGHT * 3.5 + DOWN * 1.8)

        grid_10_lbl = Text("B8A resampled (10m)\n4x4 px", font_size=16, font=FNT
                           ).next_to(grid_10, DOWN, buff=0.15)

        arrow_resample = Arrow(
            grid_20.get_right() + RIGHT * 0.2,
            grid_10.get_left() + LEFT * 0.2,
            color=YELLOW, stroke_width=4
        )

        self.play(
            FadeIn(grid_20), Write(grid_20_lbl),
            GrowArrow(arrow_resample)
        )
        self.play(FadeIn(grid_10), Write(grid_10_lbl), run_time=1)
        self.wait(2)

        stage5_objs = VGroup(
            grid_20, grid_20_lbl, grid_10, grid_10_lbl,
            arrow_resample, resample_title, affine_eq_title, affine_eq
        )
        self.play(FadeOut(stage5_objs), run_time=0.8)

        # =============================================================
        # GIAI ĐOẠN 6 — Tính toán NDVI
        # =============================================================
        t6 = Text("Giai đoạn 6: Tính NDVI (Chỉ số Thực vật)",
                   font_size=34, font=FNT).to_edge(UP)
        self.play(Transform(t1, t6))

        ndvi_f = MathTex(
            r"\text{NDVI} = \frac{\text{NIR} - \text{RED}}{\text{NIR} + \text{RED}} \;\in\;[-1,\;+1]",
            font_size=48
        ).move_to(UP * 1.5)
        self.play(Write(ndvi_f))

        n_segs = 10
        grad_colors = [
            BLUE_D, BLUE, RED, RED_B, ORANGE,
            YELLOW, GREEN_YELLOW, GREEN_B, GREEN, GREEN_D
        ]
        bar = VGroup(*[
            Rectangle(width=8 / n_segs, height=0.55)
            .set_fill(grad_colors[i], opacity=0.9)
            .set_stroke(width=0)
            for i in range(n_segs)
        ]).arrange(RIGHT, buff=0).move_to(DOWN * 0.3)
        self.play(FadeIn(bar))

        s_labels = VGroup(
            Text("-1.0\n(Nước)", font_size=16, font=FNT, color=BLUE_D
                 ).next_to(bar, DOWN, buff=0.15).align_to(bar, LEFT),
            Text("0.0\n(Đất trống)", font_size=16, font=FNT, color=YELLOW
                 ).next_to(bar, DOWN, buff=0.15),
            Text("+1.0\n(Lúa khỏe)", font_size=16, font=FNT, color=GREEN_D
                 ).next_to(bar, DOWN, buff=0.15).align_to(bar, RIGHT),
        )
        self.play(Write(s_labels))

        sample = MathTex(
            r"\text{NIR}=0.45,\;\text{RED}=0.10 \;\Rightarrow\;"
            r"\text{NDVI}=\frac{0.35}{0.55}\approx 0.636",
            font_size=28
        ).next_to(s_labels, DOWN, buff=0.4)
        self.play(Write(sample))
        self.wait(1.5)

        self.play(FadeOut(ndvi_f), FadeOut(s_labels), FadeOut(sample))

        # =============================================================
        # GIAI ĐOẠN 7 — Heatmap NDVI: Phân vùng kết quả
        # =============================================================
        t7 = Text("Giai đoạn 7: Heatmap NDVI — Phân vùng Lúa / Mặn",
                   font_size=34, font=FNT).to_edge(UP)
        self.play(Transform(t1, t7))

        hm_colors = [GREEN, GREEN_D, GREEN_YELLOW, YELLOW,
                     ORANGE, RED_B, RED, BLUE_D]
        hm_vals   = ["+0.8", "+0.6", "+0.4", "+0.2",
                     "0.0", "-0.1", "-0.2", "-0.4"]
        hm_zones  = ["Lúa\nkhỏe", "", "", "Stress",
                     "Đất\ntrống", "Mặn", "Mặn\nnặng", "Nước"]

        heatmap = VGroup()
        for ci in range(8):
            col_vg = VGroup()
            for ri in range(8):
                cidx = min(ci + ri // 4, 7)
                cell = Square(
                    side_length=0.5, fill_opacity=0.85,
                    color=hm_colors[cidx]
                ).set_stroke(WHITE, 0.5)
                col_vg.add(cell)
            col_vg.arrange(DOWN, buff=0.04)
            heatmap.add(col_vg)
        heatmap.arrange(RIGHT, buff=0.04).move_to(DOWN * 0.2)

        self.play(FadeOut(bar), FadeIn(heatmap), run_time=1.2)

        col_lb = VGroup()
        for i, (v, z) in enumerate(zip(hm_vals, hm_zones)):
            lb = Text(f"{v}\n{z}", font_size=12, font=FNT, color=hm_colors[i])
            lb.next_to(heatmap[i], DOWN, buff=0.1)
            col_lb.add(lb)
        self.play(Write(col_lb))
        self.wait(2)

        self.play(FadeOut(heatmap), FadeOut(col_lb))

        # =============================================================
        # TỔNG KẾT — Pipeline hoàn chỉnh
        # =============================================================
        summary = VGroup(
            Text("Pipeline hoàn chỉnh:", font_size=30,
                 font=FNT, color=YELLOW, weight=BOLD),
            Text("❶ RAM 1D  →  ❷ Grid 2D  →  ❸ Affine/UTM  →  ❹ WGS84 Sphere",
                 font_size=24, font=FNT),
            Text("→  ❺ Coregistration  →  ❻ NDVI float32  →  ❼ RGB Heatmap",
                 font_size=24, font=FNT),
        ).arrange(DOWN, buff=0.35).move_to(ORIGIN)

        self.play(Write(summary), run_time=2)
        self.wait(2.5)
        self.play(FadeOut(summary), FadeOut(t1))