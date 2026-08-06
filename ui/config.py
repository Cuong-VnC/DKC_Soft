# Premium QSS Stylesheet matching modern Video-Editing SaaS designs
QSS_STYLESHEET = """
QMainWindow {
    background-color: #121214;
}
QWidget {
    color: #e1e1e6;
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 12px;
}
QFrame#SidebarFrame {
    background-color: #18181b;
    border: none;
    border-right: 1px solid #27272a;
}
QFrame#RightPlayerFrame {
    background-color: #18181b;
    border: none;
    border-left: 1px solid #27272a;
}
QFrame#CenterStoryboardFrame {
    background-color: #121214;
    border: none;
}
QFrame#PlayerFrame {
    background-color: #09090b;
    border: 1px solid #27272a;
    border-radius: 8px;
}
QFrame#SceneRowFrame {
    background-color: #202024;
    border: 1px solid #2d2d34;
    border-radius: 6px;
}
QFrame#SceneRowFrame:hover {
    border-color: #007acc;
}
QPushButton {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    padding: 5px 10px;
    border-radius: 4px;
    font-weight: bold;
    color: #ffffff;
    font-size: 11px;
}
QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}
QPushButton:pressed {
    background-color: #18181b;
}
QPushButton#AddCardBtn {
    background-color: #18181b;
    border: 2px dashed #3f3f46;
    border-radius: 6px;
    color: #a1a1aa;
    font-size: 11px;
}
QPushButton#AddCardBtn:hover {
    border-color: #007acc;
    color: #007acc;
    background-color: #202024;
}
QPushButton#MiniDeleteBtn {
    background-color: #7f1d1d;
    border: none;
    color: #fca5a5;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 11px;
}
QPushButton#MiniDeleteBtn:hover {
    background-color: #b91c1c;
    color: #ffffff;
}
QComboBox, QLineEdit, QTextEdit, QPlainTextEdit, QDoubleSpinBox {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 4px;
    padding: 4px;
    color: #ffffff;
    font-size: 11px;
}
QComboBox:focus, QTextEdit:focus, QDoubleSpinBox:focus {
    border-color: #007acc;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QTabWidget::pane {
    border: 1px solid #27272a;
    background-color: #18181b;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #202024;
    border: 1px solid #27272a;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 8px;
    margin-right: 2px;
    color: #a1a1aa;
    font-weight: bold;
    font-size: 11px;
}
QTabBar::tab:selected {
    background-color: #18181b;
    border-bottom: 1px solid #18181b;
    color: #ffffff;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #27272a;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #007acc;
    width: 12px;
    height: 12px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover {
    background: #0098ff;
}
QProgressBar {
    border: 1px solid #27272a;
    border-radius: 4px;
    text-align: center;
    background-color: #18181b;
    color: #ffffff;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #007acc;
}
QScrollBar:horizontal {
    height: 8px;
    background: #18181b;
}
QScrollBar::handle:horizontal {
    background: #27272a;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #3f3f46;
}
QScrollBar:vertical {
    width: 8px;
    background: #18181b;
}
QScrollBar::handle:vertical {
    background: #27272a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #3f3f46;
}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
    border: none;
    width: 0px;
    height: 0px;
}
QScrollArea {
    background-color: #121214;
    border: none;
}
QDialog {
    background-color: #121214;
}
QComboBox QAbstractItemView {
    background-color: #18181b;
    border: 1px solid #27272a;
    selection-background-color: #007acc;
    selection-color: #ffffff;
    color: #ffffff;
}
HoverThumbnailButton {
    background-color: #121214;
    border: 1px dashed #3f3f46;
    border-radius: 4px;
    color: #a1a1aa;
    font-weight: bold;
    font-size: 11px;
}
HoverThumbnailButton:hover {
    background-color: #1a1a1e;
}
"""

LIGHT_QSS_STYLESHEET = """
QMainWindow {
    background-color: #f4f4f5;
}
QWidget {
    color: #18181b;
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 12px;
}
QFrame#SidebarFrame {
    background-color: #e4e4e7;
    border: none;
    border-right: 1px solid #d4d4d8;
}
QFrame#RightPlayerFrame {
    background-color: #e4e4e7;
    border: none;
    border-left: 1px solid #d4d4d8;
}
QFrame#CenterStoryboardFrame {
    background-color: #f4f4f5;
    border: none;
}
QFrame#PlayerFrame {
    background-color: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
}
QFrame#SceneRowFrame {
    background-color: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
}
QFrame#SceneRowFrame:hover {
    border-color: #007acc;
}
QPushButton {
    background-color: #e4e4e7;
    border: 1px solid #ccc;
    padding: 5px 10px;
    border-radius: 4px;
    font-weight: bold;
    color: #18181b;
    font-size: 11px;
}
QPushButton:hover {
    background-color: #d4d4d8;
}
QPushButton:pressed {
    background-color: #b4b4b8;
}
QPushButton#AddCardBtn {
    background-color: #ffffff;
    border: 2px dashed #ccc;
    border-radius: 6px;
    color: #71717a;
    font-size: 11px;
}
QPushButton#AddCardBtn:hover {
    border-color: #007acc;
    color: #007acc;
    background-color: #f4f4f5;
}
QPushButton#MiniDeleteBtn {
    background-color: #fca5a5;
    border: none;
    color: #7f1d1d;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 11px;
}
QPushButton#MiniDeleteBtn:hover {
    background-color: #b91c1c;
    color: #ffffff;
}
QComboBox, QLineEdit, QTextEdit, QPlainTextEdit, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 4px;
    color: #18181b;
    font-size: 11px;
}
QComboBox:focus, QTextEdit:focus, QDoubleSpinBox:focus {
    border-color: #007acc;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QTabWidget::pane {
    border: 1px solid #ccc;
    background-color: #ffffff;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #e4e4e7;
    border: 1px solid #ccc;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 8px;
    margin-right: 2px;
    color: #71717a;
    font-weight: bold;
    font-size: 11px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    border-bottom: 1px solid #ffffff;
    color: #18181b;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #ccc;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #007acc;
    width: 12px;
    height: 12px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover {
    background: #0098ff;
}
QProgressBar {
    border: 1px solid #ccc;
    border-radius: 4px;
    text-align: center;
    background-color: #ffffff;
    color: #18181b;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #007acc;
}
QScrollArea {
    background-color: #f4f4f5;
    border: none;
}
QDialog {
    background-color: #f4f4f5;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #ccc;
    selection-background-color: #007acc;
    selection-color: #ffffff;
    color: #18181b;
}
QScrollBar:horizontal {
    height: 8px;
    background: #f4f4f5;
}
QScrollBar::handle:horizontal {
    background: #d4d4d8;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #b4b4b8;
}
QScrollBar:vertical {
    width: 8px;
    background: #f4f4f5;
}
QScrollBar::handle:vertical {
    background: #d4d4d8;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #b4b4b8;
}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
    border: none;
    width: 0px;
    height: 0px;
}
HoverThumbnailButton {
    background-color: #e4e4e7;
    border: 1px dashed #ccc;
    border-radius: 4px;
    color: #71717a;
    font-weight: bold;
    font-size: 11px;
}
HoverThumbnailButton:hover {
    background-color: #d4d4d8;
}
"""

TRANSLATIONS = {
    "vi": {
        "brand": "AI Drawing Generator",
        "tab_tts": "Giọng TTS",
        "tab_style": "Nét Vẽ",
        "tab_audio": "Nhạc Cam",
        "tab_export": "Xuất Video",
        "open_proj": "Mở Dự Án",
        "save_proj": "Lưu Dự Án",
        "settings": "Cài Đặt",
        "storyboard_title": "BẢNG PHÂN CẢNH (STORYBOARD)",
        "preview_title": "XEM TRƯỚC VIDEO",
        "render_btn": "SINH VIDEO VẼ TRANH",
        "pause_btn": "Tạm Dừng",
        "resume_btn": "Tiếp Tục",
        "cancel_btn": "Hủy",
        "log_title": "NHẬT KÝ HỆ THỐNG",
        "lbl_progress_ready": "Sẵn sàng.",
        "add_scene_btn": "+ Thêm Cảnh Mới",
        "scene_label": "Cảnh #",
        "opt_resolution": "Độ phân giải:",
        "opt_fps": "Khung hình (FPS):",
        "opt_export_dir": "Thư mục xuất video:",
        "opt_export_mode": "Chế độ xuất video:",
        "opt_export_merged": "Video đã ghép",
        "opt_export_scenes": "Video từng cảnh",
        "opt_choose": "Chọn",
        "opt_voice": "Giọng Đọc (Voice):",
        "opt_tts_model": "Công nghệ TTS:",
        "opt_rate": "Tốc độ đọc:",
        "opt_pitch": "Tông giọng (Pitch):",
        "opt_pen": "Cọ vẽ:",
        "opt_bg": "Nền giấy:",
        "opt_color": "Màu nét vẽ:",
        "opt_width": "Độ dày nét:",
        "opt_color_mode": "Chế độ tô màu:",
        "opt_draw_direction": "Hướng nét vẽ:",
        "opt_bgm": "Nhạc nền (BGM):",
        "opt_volume_voice": "Âm nhạc:",
        "opt_volume_voice_read": "Âm đọc:",
        "opt_volume_bgm": "Âm lượng nhạc nền:",
        "opt_cam": "Camera di chuyển theo nét vẽ",
        "opt_smart_grid": "Tối ưu nét vẽ thông minh (Grid)",
        "opt_slide": "Hiệu ứng cuộn trang khi chuyển cảnh",
        "opt_color_style": "Cách tô màu:",
        "tab_mode_multi": "Video từng ảnh",
        "tab_mode_single": "Video 1 ảnh",
        "tab_mode_settings": "Cài đặt",
        "single_title": "TẠO VIDEO TỪ MỘT ẢNH",
        "single_image_label": "Chọn hình ảnh đầu vào:",
        "single_script_label": "Nhập kịch bản (Script):",
        "single_no_image": "Chưa chọn hình ảnh nào",
        "settings_title": "CÀI ĐẶT HỆ THỐNG",
        "settings_lang": "Ngôn ngữ:",
        "settings_theme": "Giao diện:",
        "bulk_upload": "Tải lên nhiều ảnh & Script",
        "logo_upload": "Tải Logo",
        "logo_pos": "Vị trí Logo",
        "logo_del": "Xóa Logo",
        "logo_title": "Quản lý Logo:",
        "transition": "Chuyển cảnh"
    },
    "en": {
        "brand": "AI Drawing Generator",
        "tab_tts": "TTS Voice",
        "tab_style": "Brush Style",
        "tab_audio": "BGM & Cam",
        "tab_export": "Export",
        "open_proj": "Open Project",
        "save_proj": "Save Project",
        "settings": "Settings",
        "storyboard_title": "STORYBOARD TIMELINE",
        "preview_title": "VIDEO PREVIEW",
        "render_btn": "GENERATE VIDEO",
        "pause_btn": "Pause",
        "resume_btn": "Resume",
        "cancel_btn": "Cancel",
        "log_title": "SYSTEM LOGS",
        "lbl_progress_ready": "Ready.",
        "add_scene_btn": "+ Add New Scene",
        "scene_label": "Scene #",
        "opt_resolution": "Resolution:",
        "opt_fps": "Frame Rate (FPS):",
        "opt_export_dir": "Export Directory:",
        "opt_export_mode": "Video export mode:",
        "opt_export_merged": "Merged video",
        "opt_export_scenes": "Individual scenes",
        "opt_choose": "Browse",
        "opt_voice": "TTS Voice Speaker:",
        "opt_tts_model": "TTS Engine:",
        "opt_rate": "Speech Rate:",
        "opt_pitch": "Voice Pitch:",
        "opt_pen": "Brush style:",
        "opt_bg": "Canvas background:",
        "opt_color": "Stroke Color:",
        "opt_width": "Stroke Width:",
        "opt_color_mode": "Coloring Mode:",
        "opt_draw_direction": "Drawing direction:",
        "opt_bgm": "Background Music (BGM):",
        "opt_volume_voice": "Music:",
        "opt_volume_voice_read": "Voice:",
        "opt_volume_bgm": "BGM Volume:",
        "opt_cam": "Camera follows drawing stroke",
        "opt_smart_grid": "Optimize drawing order (Grid)",
        "opt_slide": "Page curl slide transitions",
        "opt_color_style": "Coloring Style:",
        "tab_mode_multi": "Multi-Image Video",
        "tab_mode_single": "Single Image Video",
        "tab_mode_settings": "Settings",
        "single_title": "SINGLE IMAGE VIDEO GENERATOR",
        "single_image_label": "Select Input Image:",
        "single_script_label": "Enter Script (Narration):",
        "single_no_image": "No image selected",
        "settings_title": "SYSTEM SETTINGS",
        "settings_lang": "Language:",
        "settings_theme": "Theme:",
        "bulk_upload": "Bulk Upload Images & Script",
        "logo_upload": "Upload Logo",
        "logo_pos": "Position Logo",
        "logo_del": "Delete Logo",
        "logo_title": "Logo Management:",
        "transition": "Transition"
    }
}

COLOR_STYLES_MAP = {
    "vi": [
        ("Tô chéo từ trái sang phải", "diagonal_l2r"),
        ("Tô chéo từ phải sang trái", "diagonal_r2l"),
        ("Tô thẳng từ trái sang phải", "straight_l2r"),
        ("Tô thẳng từ phải sang trái", "straight_r2l"),
        ("Hiện ngay lập tức", "immediate"),
        ("Hiện màu chậm", "gradual"),
        ("Sử dụng ngẫu nhiên phong cách tô màu", "random")
    ],
    "en": [
        ("Diagonal: Left to Right", "diagonal_l2r"),
        ("Diagonal: Right to Left", "diagonal_r2l"),
        ("Straight: Left to Right", "straight_l2r"),
        ("Straight: Right to Left", "straight_r2l"),
        ("Show Immediately", "immediate"),
        ("Show Gradually", "gradual"),
        ("Random Style", "random")
    ]
}

COLOR_OPTIONS_MAP = {
    "vi": [
        ("Chỉ vẽ nét", "Only Outline"),
        ("Vẽ nét rồi tô màu", "Outline then Color"),
        ("Vẽ nét và tô màu", "Outline and Color"),
        ("Chỉ tô màu", "Only Color")
    ],
    "en": [
        ("Only Outline", "Only Outline"),
        ("Outline then Color", "Outline then Color"),
        ("Outline and Color", "Outline and Color"),
        ("Only Color", "Only Color")
    ]
}

DRAW_DIRECTIONS_MAP = {
    "vi": [
        ("Từ Trái sang Phải", "left_to_right"),
        ("Từ Phải sang Trái", "right_to_left"),
        ("Từ Trên xuống Dưới", "top_to_bottom"),
        ("Từ Dưới lên Trên", "bottom_to_top")
    ],
    "en": [
        ("Left to Right", "left_to_right"),
        ("Right to Left", "right_to_left"),
        ("Top to Bottom", "top_to_bottom"),
        ("Bottom to Top", "bottom_to_top")
    ]
}
