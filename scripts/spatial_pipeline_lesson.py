"""Bài học Manim Community 0.21.0, không cần LaTeX hoặc dữ liệu vệ tinh.

Render tất cả:
    python -m manim -ql scripts/spatial_pipeline_lesson.py WindowedNDVI GridAlignment MosaicAndArea
Render một chương chất lượng cao:
    python -m manim -qh scripts/spatial_pipeline_lesson.py GridAlignment

Text dùng Pango; VGroup nhóm hình để bố trí/chuyển động đồng bộ.
Scene.construct là timeline. self.play chạy animation; self.wait dành thời
gian đọc. Không chỉnh config toàn cục để -ql/-qh/--fps vẫn có hiệu lực.
Các ma trận nhỏ là dữ liệu giảng dạy, không phải ảnh Sentinel thật.
"""
import numpy as np
from manim import (
    Scene, VGroup, Text, Square, RoundedRectangle, SurroundingRectangle,
    Arrow, FadeIn, FadeOut, Create, Write, Transform, TransformFromCopy,
    Indicate, LaggedStart, UP, DOWN, RIGHT, LEFT,
)

BG = '#0F172A'
FG = '#E2E8F0'
BLUE = '#38BDF8'
GREEN = '#4ADE80'
RED = '#FB7185'
YELLOW = '#FACC15'
MUTED = '#94A3B8'


def label(text, size=26, color=FG):
    """Text thay cho MathTex: máy học không cần cài một bộ LaTeX lớn."""
    return Text(text, font='Arial', font_size=size, color=color)


def grid(values, cell_size=.72, color=BLUE):
    """Trả về grid và từng cell theo thứ tự row-major, giống NumPy C-order."""
    cells = VGroup()
    rows, cols = len(values), len(values[0])
    for row in range(rows):
        for col in range(cols):
            value = values[row][col]
            square = Square(side_length=cell_size, stroke_color=color, stroke_width=1.5)
            square.set_fill(color, opacity=.10)
            text = label(str(value), size=20 if cell_size < .8 else 25)
            if text.width > cell_size*.85:
                text.scale_to_fit_width(cell_size*.85)
            # Mỗi cell = [Square, Text]; animation có thể tô riêng Square.
            cell = VGroup(square, text)
            cell.move_to([(col-(cols-1)/2)*cell_size, ((rows-1)/2-row)*cell_size, 0])
            cells.add(cell)
    return cells


class LessonScene(Scene):
    """Lớp nền dùng chung tiêu đề và phụ đề, tránh lặp layout ở mỗi chương."""
    def setup(self):
        self.camera.background_color = BG

    def heading(self, title, subtitle):
        self.title = label(title, 36).to_edge(UP, buff=.35)
        self.subtitle = label(subtitle, 21, MUTED).next_to(self.title, DOWN, buff=.18)
        self.play(Write(self.title), FadeIn(self.subtitle))

    def caption(self, text):
        new = label(text, 23).to_edge(DOWN, buff=.4)
        if new.width > 13:
            new.scale_to_fit_width(13)
        if hasattr(self, 'footnote'):
            # Transform giữ cùng đối tượng trên scene, thay hình học/nội dung.
            self.play(Transform(self.footnote, new), run_time=.5)
        else:
            self.footnote = new
            self.play(FadeIn(new), run_time=.5)


class WindowedNDVI(LessonScene):
    """Chương 1: cửa sổ nhỏ -> calibration -> mask -> NDVI -> ghi rồi giải phóng."""
    def construct(self):
        self.heading('01  |  Một chunk đi qua pipeline', 'Đọc ít dữ liệu, tính vectorized, ghi ngay xuống đĩa')
        values = np.arange(16).reshape(4, 4).tolist()
        disk = grid(values, .65).move_to(LEFT*4.5)
        disk_title = label('Raster trên đĩa', 25).next_to(disk, UP)
        ram = RoundedRectangle(width=3.3, height=2.6, corner_radius=.15,
                               stroke_color=YELLOW).move_to(LEFT*.2)
        ram_title = label('RAM: một chunk', 25, YELLOW).next_to(ram, UP)
        output = grid([['·']*4 for _ in range(4)], .65, GREEN).move_to(RIGHT*4.3)
        output_title = label('GeoTIFF đầu ra', 25, GREEN).next_to(output, UP)
        arrows = VGroup(Arrow(disk.get_right(), ram.get_left(), buff=.2, color=BLUE),
                        Arrow(ram.get_right(), output.get_left(), buff=.2, color=GREEN))
        self.play(FadeIn(disk), FadeIn(disk_title), Create(ram), FadeIn(ram_title),
                  FadeIn(output), FadeIn(output_title), Create(arrows))
        self.caption('Window(col, row, width, height) xác định phần ảnh cần đọc.')
        # Các chunk 2x2 được duyệt row-major, đúng ý tưởng vòng lặp thật.
        for positions in ([0,1,4,5], [2,3,6,7], [8,9,12,13], [10,11,14,15]):
            selected = VGroup(*[disk[i] for i in positions])
            highlight = SurroundingRectangle(selected, color=YELLOW, buff=.04)
            in_ram = selected.copy().move_to(ram)
            self.play(Create(highlight), TransformFromCopy(selected, in_ram), run_time=.55)
            self.play(*[output[i][0].animate.set_fill(GREEN, opacity=.5) for i in positions], run_time=.35)
            self.play(FadeOut(in_ram), FadeOut(highlight), run_time=.3)
        self.caption('RAM phụ thuộc chunk², không phụ thuộc tổng số pixel của tile.')
        self.wait(2)
        self.play(*[FadeOut(m) for m in [disk, disk_title, ram, ram_title, output, output_title, arrows]])
        # Các số dùng cùng quan hệ calibration như pipeline, không dùng DN thẳng.
        lines = VGroup(
            label('DN: RED = 2000, NIR = 4000', 30, BLUE),
            label('reflectance = DN × 0.0001 − 0.1', 28, YELLOW),
            label('RED = 0.1, NIR = 0.3', 30),
            label('NDVI = (0.3 − 0.1) / (0.3 + 0.1) = 0.5', 30, GREEN),
        ).arrange(DOWN, buff=.42)
        self.play(LaggedStart(*[FadeIn(line, shift=UP*.15) for line in lines], lag_ratio=.5))
        self.caption('np.divide(..., out=result, where=valid): pixel bị mây hoặc mẫu số 0 giữ NaN.')
        self.wait(4)


class GridAlignment(LessonScene):
    """Chương 2: nghịch đảo tọa độ; tại sao không thể chỉ repeat mảng SCL."""
    def construct(self):
        self.heading('02  |  Ghép đúng vị trí, không chỉ đúng shape', 'SCL 20 m và RED/NIR 10 m nhìn cùng một mặt đất')
        source = grid([[4, 9], [6, 4]], 1.2).move_to(LEFT*4)
        target = grid([['?']*4 for _ in range(4)], .6).move_to(RIGHT*4)
        names = VGroup(label('SCL · 20 m', 26).next_to(source, UP),
                       label('Lưới đích · 10 m', 26).next_to(target, UP))
        algorithm = VGroup(label('Tâm pixel đích', 22, YELLOW),
                           label('→ tọa độ mặt đất', 22),
                           label('→ CRS nguồn', 22),
                           label('→ inverse affine', 22),
                           label('→ floor(row, col)', 22, GREEN)).arrange(DOWN, buff=.20)
        self.play(FadeIn(source), FadeIn(target), FadeIn(names), FadeIn(algorithm))
        self.caption('Mỗi pixel đích hỏi: tâm của tôi nằm trong pixel nguồn nào?')
        groups = [[0,1,4,5], [2,3,6,7], [8,9,12,13], [10,11,14,15]]
        for i, (value, positions) in enumerate(zip([4,9,6,4], groups)):
            color = RED if value == 9 else GREEN
            self.play(Indicate(source[i], color=YELLOW), run_time=.5)
            animations = []
            for p in positions:
                new = label(str(value), 20, color).move_to(target[p][1])
                animations.extend([Transform(target[p][1], new),
                                   target[p][0].animate.set_fill(color, opacity=.22)])
            self.play(*animations, run_time=.6)
        self.caption('Lớp 9 là mây: loại cả 4 pixel đích. Lớp 4 và 6 được giữ trong NDVI.')
        self.wait(2)
        note = label('Chỉ khi lưới thẳng hàng thì ví dụ này trông giống repeat(2).', 24, YELLOW)
        note.move_to(DOWN*2.1)
        self.play(FadeIn(note))
        self.caption('Khác UTM zone: pyproj đổi tọa độ; NumPy vẫn tự chọn pixel nearest-neighbor.')
        self.wait(4)


class MosaicAndArea(LessonScene):
    """Chương 3: ưu tiên nguồn, lấp nodata, provenance và diện tích không trùng."""
    def construct(self):
        self.heading('03  |  Hai tile chồng nhau, mỗi pixel chỉ tính một lần',
                     'Lưới chung EPSG:6933 · ưu tiên gần ngày mục tiêu → ít mây → scene ID')
        a = grid([['0.2', 'NaN', '0.2'], ['0.2', '0.2', 'NaN']], .85, BLUE).move_to(LEFT*4.5+UP*.3)
        b = grid([['0.8', '0.8', '0.8'], ['0.8', '0.8', '0.8']], .85, YELLOW).move_to(UP*.3)
        result = grid([['?', '?', '?'], ['?', '?', '?']], .85, GREEN).move_to(RIGHT*4.5+UP*.3)
        names = VGroup(label('A · đúng ngày', 24, BLUE).next_to(a, UP),
                       label('B · lệch 1 ngày', 24, YELLOW).next_to(b, UP),
                       label('Mosaic', 24, GREEN).next_to(result, UP))
        self.play(FadeIn(a), FadeIn(b), FadeIn(result), FadeIn(names))
        self.caption('A được xét trước. B chỉ điền những ô A không có quan sát hợp lệ.')
        values, winners = [.2, .8, .2, .2, .2, .8], ['A','B','A','A','A','B']
        for i, (value, winner) in enumerate(zip(values, winners)):
            origin = a if winner == 'A' else b
            color = BLUE if winner == 'A' else YELLOW
            self.play(Indicate(origin[i], color=color),
                      Transform(result[i][1], label(str(value), 25, color).move_to(result[i][1])),
                      result[i][0].animate.set_fill(color, opacity=.2), run_time=.45)
        provenance = label('source_index = [1, 2, 1; 1, 1, 2]', 26, GREEN).move_to(DOWN*1.45)
        self.play(Write(provenance))
        self.caption('Lưu source_index.tif để truy ngược scene và ngày chụp của từng pixel.')
        self.wait(2)
        area = label('6 pixel × 10 m × 10 m / 10 000 = 0.06 ha', 28, YELLOW).move_to(DOWN*2.2)
        self.play(Write(area))
        self.caption('Không cộng 4 pixel của A + 6 pixel của B: 4 vị trí đã bị đếm hai lần.')
        self.wait(3)
        self.caption('AOI và rice mask chọn vùng; NaN giảm coverage, không tự biến thành “không có lúa”.')
        self.wait(4)
