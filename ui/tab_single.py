import os
from typing import Dict, Any, List, Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QSlider, QCheckBox, QProgressBar, QPlainTextEdit,
    QFrame, QColorDialog, QFileDialog, QSplitter, QSizePolicy, QTabWidget,
    QStyle
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap

from ui.preview_canvas import PreviewCanvas
from ui.config import TRANSLATIONS, COLOR_STYLES_MAP
from ui.logo_dialog import LogoPositionDialog
from engine.project import ProjectManager
from PySide6.QtWidgets import QMessageBox

class SingleVideoTab(QWidget):
    def __init__(self, dirs: Dict[str, str], current_lang: str, voices_list: List[Dict[str, Any]],
                 start_render_cb: Callable[[], None], pause_render_cb: Callable[[], None],
                 resume_render_cb: Callable[[], None], cancel_render_cb: Callable[[], None], parent=None):
        super().__init__(parent)
        self.dirs = dirs
        self.current_lang = current_lang
        self.voices_list = voices_list
        self.edge_voices: List[Dict[str, Any]] = []
        self.capcut_voices: List[Dict[str, Any]] = []
        self.start_render_cb = start_render_cb
        self.pause_render_cb = pause_render_cb
        self.resume_render_cb = resume_render_cb
        self.cancel_render_cb = cancel_render_cb
        
        self.single_image_path = ""
        self.pen_color_rgb = [0, 0, 0]
        self.logos_list: List[Dict[str, Any]] = []
        self.current_theme = "dark"
        
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.splitter_single = QSplitter(Qt.Horizontal)
        self.splitter_single.setObjectName("MainSplitterSingle")
        self.splitter_single.setStyleSheet("""
            QSplitter::handle {
                background-color: #27272a;
                width: 4px;
            }
            QSplitter::handle:hover {
                background-color: #007acc;
            }
        """)
        
        # 1. Left Sidebar
        sidebar = self._build_settings_sidebar()
        self.splitter_single.addWidget(sidebar)
        
        # 2. Center Panel (Image picker and script textbox)
        center_panel = self._build_center_single_panel()
        self.splitter_single.addWidget(center_panel)
        
        # 3. Right Sidebar
        right_panel = self._build_right_panel()
        self.splitter_single.addWidget(right_panel)
        
        self.splitter_single.setSizes([320, 640, 320])
        layout.addWidget(self.splitter_single)
        
        self.update_language(self.current_lang)
        self.load_existing_custom_assets()
        self.update_delete_buttons_state()
        self.refresh_canvas_preview()

    def _build_settings_sidebar(self) -> QFrame:
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("SidebarFrame")
        sidebar_frame.setMinimumWidth(280)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(10, 12, 10, 12)
        sidebar_layout.setSpacing(10)
        
        self.lbl_brand = QLabel("AI Drawing Generator")
        self.lbl_brand.setStyleSheet("font-weight: bold; font-size: 14px;")
        sidebar_layout.addWidget(self.lbl_brand)
        
        self.tabs = QTabWidget()
        self._build_tab_tts()
        self._build_tab_style()
        self._build_tab_audio()
        self._build_tab_export()
        
        sidebar_layout.addWidget(self.tabs)
        
        proj_actions_frame = QFrame()
        proj_actions_frame.setStyleSheet("background: transparent; border: none;")
        proj_actions_layout = QGridLayout(proj_actions_frame)
        proj_actions_layout.setContentsMargins(0, 0, 0, 0)
        proj_actions_layout.setSpacing(6)
        
        self.btn_load_proj = QPushButton()
        self.btn_load_proj.clicked.connect(self.load_project_dialog)
        proj_actions_layout.addWidget(self.btn_load_proj, 0, 0)
        
        self.btn_save_proj = QPushButton()
        self.btn_save_proj.clicked.connect(self.save_project_dialog)
        proj_actions_layout.addWidget(self.btn_save_proj, 0, 1)
        
        sidebar_layout.addWidget(proj_actions_frame)
        return sidebar_frame

    def _build_right_panel(self) -> QFrame:
        right_frame = QFrame()
        right_frame.setObjectName("RightPlayerFrame")
        right_frame.setMinimumWidth(300)
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        
        self.lbl_preview_title = QLabel()
        self.lbl_preview_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #a1a1aa;")
        right_layout.addWidget(self.lbl_preview_title)
        
        viewport_frame = QFrame()
        viewport_frame.setObjectName("PlayerFrame")
        viewport_frame.setFixedHeight(180)
        viewport_layout = QVBoxLayout(viewport_frame)
        viewport_layout.setContentsMargins(4, 4, 4, 4)
        
        self.preview_canvas = PreviewCanvas()
        viewport_layout.addWidget(self.preview_canvas)
        right_layout.addWidget(viewport_frame)
        
        self.lbl_progress = QLabel()
        self.lbl_progress.setStyleSheet("font-weight: 500; color: #a1a1aa;")
        right_layout.addWidget(self.lbl_progress)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        right_layout.addWidget(self.progress_bar)
        
        btn_grid = QGridLayout()
        btn_grid.setContentsMargins(0, 4, 0, 0)
        btn_grid.setSpacing(6)
        
        self.btn_render = QPushButton()
        self.btn_render.setObjectName("RenderButton")
        self.btn_render.clicked.connect(self.start_render_cb)
        btn_grid.addWidget(self.btn_render, 0, 0)
        
        self.btn_cancel = QPushButton()
        self.btn_cancel.setObjectName("CancelButton")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_render_cb)
        btn_grid.addWidget(self.btn_cancel, 0, 1)
        
        self.btn_pause = QPushButton()
        self.btn_pause.setObjectName("PauseButton")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.pause_render_cb)
        btn_grid.addWidget(self.btn_pause, 1, 0)
        
        self.btn_resume = QPushButton()
        self.btn_resume.setObjectName("ResumeButton")
        self.btn_resume.setEnabled(False)
        self.btn_resume.clicked.connect(self.resume_render_cb)
        btn_grid.addWidget(self.btn_resume, 1, 1)
        
        right_layout.addLayout(btn_grid)
        
        self.lbl_log_title = QLabel()
        self.lbl_log_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #71717a; margin-top: 8px;")
        right_layout.addWidget(self.lbl_log_title)
        
        self.txt_logs = QPlainTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setStyleSheet("font-family: 'Courier New', monospace; font-size: 11px; background-color: #09090b; border: 1px solid #27272a;")
        right_layout.addWidget(self.txt_logs, stretch=1)
        
        return right_frame

    def _build_center_single_panel(self) -> QFrame:
        center_frame = QFrame()
        center_frame.setObjectName("CenterStoryboardFrame")
        center_layout = QVBoxLayout(center_frame)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(12)
        
        self.lbl_single_title = QLabel("TẠO VIDEO TỪ MỘT ẢNH")
        self.lbl_single_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #a1a1aa;")
        center_layout.addWidget(self.lbl_single_title)
        
        content_frame = QFrame()
        content_frame.setObjectName("SceneRowFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(12)
        
        self.lbl_single_image = QLabel("Chọn hình ảnh đầu vào:")
        self.lbl_single_image.setStyleSheet("font-weight: bold;")
        content_layout.addWidget(self.lbl_single_image)
        
        hbox_img = QHBoxLayout()
        hbox_img.setSpacing(12)
        
        self.single_img_prev = QPushButton("+ Chọn Ảnh")
        self.single_img_prev.setObjectName("SingleImagePrev")
        self.single_img_prev.setProperty("hasImage", "false")
        self.single_img_prev.setFixedSize(160, 90)
        self.single_img_prev.clicked.connect(self._select_single_image)
        hbox_img.addWidget(self.single_img_prev)
        
        vbox_img_info = QVBoxLayout()
        self.lbl_single_filename = QLabel("Chưa chọn hình ảnh nào")
        self.lbl_single_filename.setStyleSheet("color: #a1a1aa; font-style: italic;")
        vbox_img_info.addWidget(self.lbl_single_filename)
        
        self.btn_single_choose = QPushButton("Chọn")
        self.btn_single_choose.clicked.connect(self._select_single_image)
        self.btn_single_choose.setFixedWidth(80)
        vbox_img_info.addWidget(self.btn_single_choose)
        vbox_img_info.addStretch()
        
        hbox_img.addLayout(vbox_img_info)
        content_layout.addLayout(hbox_img)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background-color: #27272a; height: 1px; border: none;")
        content_layout.addWidget(sep)
        
        self.lbl_single_script = QLabel("Nhập kịch bản (Script):")
        self.lbl_single_script.setStyleSheet("font-weight: bold;")
        content_layout.addWidget(self.lbl_single_script)
        
        self.single_txt_script = QTextEdit()
        self.single_txt_script.setPlaceholderText("Nhập kịch bản thuyết minh tại đây...")
        self.single_txt_script.setMinimumHeight(150)
        content_layout.addWidget(self.single_txt_script)
        
        center_layout.addWidget(content_frame)
        center_layout.addStretch()
        
        return center_frame

    def _select_single_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn Hình Ảnh", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)")
        if file_path:
            self.single_image_path = file_path
            filename = os.path.basename(file_path)
            self.lbl_single_filename.setText(filename)
            self.lbl_single_filename.setStyleSheet("color: #007acc; font-weight: bold;")
            
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(QSize(156, 86), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.single_img_prev.setIcon(QIcon(scaled))
                self.single_img_prev.setIconSize(scaled.size())
                self.single_img_prev.setText("")
                self.single_img_prev.setProperty("hasImage", "true")
                self.single_img_prev.style().unpolish(self.single_img_prev)
                self.single_img_prev.style().polish(self.single_img_prev)

    def _build_tab_tts(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        self.lbl_tts_model = QLabel()
        layout.addWidget(self.lbl_tts_model)
        
        self.cmb_tts_model = QComboBox()
        self.cmb_tts_model.addItem("Edge-TTS")
        self.cmb_tts_model.addItem("CapCut TTS")
        self.cmb_tts_model.currentIndexChanged.connect(self.update_voice_combobox)
        layout.addWidget(self.cmb_tts_model)
        
        self.lbl_voice_hdr = QLabel("Giọng Đọc (Voice):")
        layout.addWidget(self.lbl_voice_hdr)
        self.cmb_voice = QComboBox()
        self.cmb_voice.addItem("Đang tải danh sách giọng đọc...")
        layout.addWidget(self.cmb_voice)
        
        hbox_rate = QHBoxLayout()
        self.lbl_rate_hdr = QLabel("Tốc độ đọc:")
        hbox_rate.addWidget(self.lbl_rate_hdr)
        self.lbl_rate_val = QLabel("+0%")
        self.lbl_rate_val.setStyleSheet("font-weight: bold; color: #007acc;")
        hbox_rate.addWidget(self.lbl_rate_val, Qt.AlignRight)
        layout.addLayout(hbox_rate)
        
        self.sld_rate = QSlider(Qt.Horizontal)
        self.sld_rate.setRange(-50, 50)
        self.sld_rate.setValue(0)
        self.sld_rate.valueChanged.connect(lambda v: self.lbl_rate_val.setText(f"{v:+}%"))
        layout.addWidget(self.sld_rate)
        
        hbox_pitch = QHBoxLayout()
        self.lbl_pitch_hdr = QLabel("Tông giọng (Pitch):")
        hbox_pitch.addWidget(self.lbl_pitch_hdr)
        self.lbl_pitch_val = QLabel("+0Hz")
        self.lbl_pitch_val.setStyleSheet("font-weight: bold; color: #007acc;")
        hbox_pitch.addWidget(self.lbl_pitch_val, Qt.AlignRight)
        layout.addLayout(hbox_pitch)
        
        self.sld_pitch = QSlider(Qt.Horizontal)
        self.sld_pitch.setRange(-20, 20)
        self.sld_pitch.setValue(0)
        self.sld_pitch.valueChanged.connect(lambda v: self.lbl_pitch_val.setText(f"{v:+}Hz"))
        layout.addWidget(self.sld_pitch)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Giọng TTS")

    def _build_tab_style(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        vbox_pen = QVBoxLayout()
        self.lbl_pen_hdr = QLabel("Cọ vẽ:")
        vbox_pen.addWidget(self.lbl_pen_hdr)
        
        hbox_pen_ctrl = QHBoxLayout()
        self.cmb_pen = QComboBox()
        self.cmb_pen.addItem("Pencil", "Pencil")
        self.cmb_pen.addItem("Ink Pen", "Ink Pen")
        self.cmb_pen.addItem("Marker", "Marker")
        self.cmb_pen.addItem("Brush", "Brush")
        self.cmb_pen.setCurrentIndex(1)
        hbox_pen_ctrl.addWidget(self.cmb_pen)
        
        vbox_pen.addLayout(hbox_pen_ctrl)
        layout.addLayout(vbox_pen)
        
        vbox_bg = QVBoxLayout()
        self.lbl_bg_hdr = QLabel("Nền giấy:")
        vbox_bg.addWidget(self.lbl_bg_hdr)
        
        hbox_bg_ctrl = QHBoxLayout()
        self.cmb_bg = QComboBox()
        self.cmb_bg.addItem("Whiteboard", "Whiteboard")
        self.cmb_bg.addItem("Blackboard", "Blackboard")
        self.cmb_bg.addItem("Old Paper", "Old Paper")
        self.cmb_bg.addItem("Canvas", "Canvas")
        self.cmb_bg.addItem("Paper Texture", "Paper Texture")
        self.cmb_bg.setCurrentIndex(0)
        hbox_bg_ctrl.addWidget(self.cmb_bg)
        
        vbox_bg.addLayout(hbox_bg_ctrl)
        layout.addLayout(vbox_bg)
        
        hbox_color_mode = QHBoxLayout()
        vbox_color = QVBoxLayout()
        self.lbl_color_hdr = QLabel("Màu nét vẽ:")
        vbox_color.addWidget(self.lbl_color_hdr)
        color_row = QHBoxLayout()
        self.btn_color_pick = QPushButton("Chọn Màu")
        self.btn_color_pick.clicked.connect(self._select_pen_color)
        color_row.addWidget(self.btn_color_pick)
        self.frame_color_prev = QFrame()
        self.frame_color_prev.setFixedSize(18, 18)
        self.frame_color_prev.setStyleSheet("background-color: black; border: 1px solid white; border-radius: 3px;")
        color_row.addWidget(self.frame_color_prev)
        vbox_color.addLayout(color_row)
        hbox_color_mode.addLayout(vbox_color)
        
        vbox_mode = QVBoxLayout()
        self.lbl_colormode_hdr = QLabel("Chế độ tô màu:")
        vbox_mode.addWidget(self.lbl_colormode_hdr)
        self.cmb_color_opt = QComboBox()
        self.cmb_color_opt.addItems(["Only Outline", "Outline then Color", "Outline and Color"])
        self.cmb_color_opt.setCurrentText("Outline then Color")
        vbox_mode.addWidget(self.cmb_color_opt)
        hbox_color_mode.addLayout(vbox_mode)
        layout.addLayout(hbox_color_mode)
        
        hbox_width = QHBoxLayout()
        self.lbl_width_hdr = QLabel("Độ dày nét:")
        hbox_width.addWidget(self.lbl_width_hdr)
        self.lbl_width_val = QLabel("4.0px")
        self.lbl_width_val.setStyleSheet("font-weight: bold; color: #007acc;")
        hbox_width.addWidget(self.lbl_width_val, Qt.AlignRight)
        layout.addLayout(hbox_width)
        
        self.sld_width = QSlider(Qt.Horizontal)
        self.sld_width.setRange(10, 100)
        self.sld_width.setValue(40)
        self.sld_width.valueChanged.connect(lambda v: self.lbl_width_val.setText(f"{v/10.0:.1f}px"))
        self.sld_width.valueChanged.connect(lambda: self.refresh_canvas_preview())
        layout.addWidget(self.sld_width)
        
        self.cmb_pen.currentIndexChanged.connect(self.update_delete_buttons_state)
        self.cmb_bg.currentIndexChanged.connect(self.update_delete_buttons_state)
        self.cmb_pen.currentIndexChanged.connect(self.refresh_canvas_preview)
        self.cmb_bg.currentIndexChanged.connect(self.refresh_canvas_preview)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Nét Vẽ")

    def _build_tab_audio(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        self.lbl_bgm_hdr = QLabel("Nhạc nền (BGM):")
        layout.addWidget(self.lbl_bgm_hdr)
        
        hbox_music = QHBoxLayout()
        self.entry_bgm = QTextEdit()
        self.entry_bgm.setMaximumHeight(28)
        self.entry_bgm.setPlaceholderText("Đường dẫn file MP3...")
        self.entry_bgm.setLineWrapMode(QTextEdit.NoWrap)
        hbox_music.addWidget(self.entry_bgm)
        self.btn_bgm_browse = QPushButton("Chọn")
        self.btn_bgm_browse.clicked.connect(self._select_bg_music)
        hbox_music.addWidget(self.btn_bgm_browse)
        layout.addLayout(hbox_music)
        
        vbox_mvol = QVBoxLayout()
        hbox_mvol_lbl = QHBoxLayout()
        self.lbl_vvol_hdr = QLabel("Âm nhạc:")
        hbox_mvol_lbl.addWidget(self.lbl_vvol_hdr)
        self.lbl_mvol_val = QLabel("15%")
        self.lbl_mvol_val.setStyleSheet("font-weight: bold; color: #007acc;")
        hbox_mvol_lbl.addWidget(self.lbl_mvol_val, Qt.AlignRight)
        vbox_mvol.addLayout(hbox_mvol_lbl)
        self.sld_mvol = QSlider(Qt.Horizontal)
        self.sld_mvol.setRange(0, 100)
        self.sld_mvol.setValue(15)
        self.sld_mvol.valueChanged.connect(lambda v: self.lbl_mvol_val.setText(f"{v}%"))
        vbox_mvol.addWidget(self.sld_mvol)
        layout.addLayout(vbox_mvol)
        
        vbox_vvol = QVBoxLayout()
        hbox_vvol_lbl = QHBoxLayout()
        self.lbl_mvol_hdr = QLabel("Âm đọc:")
        hbox_vvol_lbl.addWidget(self.lbl_mvol_hdr)
        self.lbl_vvol_val = QLabel("100%")
        self.lbl_vvol_val.setStyleSheet("font-weight: bold; color: #007acc;")
        hbox_vvol_lbl.addWidget(self.lbl_vvol_val, Qt.AlignRight)
        vbox_vvol.addLayout(hbox_vvol_lbl)
        self.sld_vvol = QSlider(Qt.Horizontal)
        self.sld_vvol.setRange(0, 100)
        self.sld_vvol.setValue(100)
        self.sld_vvol.valueChanged.connect(lambda v: self.lbl_vvol_val.setText(f"{v}%"))
        vbox_vvol.addWidget(self.sld_vvol)
        layout.addLayout(vbox_vvol)
        
        self.lbl_color_style_hdr = QLabel("Cách tô màu:")
        layout.addWidget(self.lbl_color_style_hdr)
        
        self.cmb_color_style = QComboBox()
        layout.addWidget(self.cmb_color_style)
        
        self.sw_camera = QCheckBox("Camera di chuyển theo nét vẽ")
        self.sw_camera.setChecked(True)
        layout.addWidget(self.sw_camera)
        
        self.sw_smart_order = QCheckBox("Tối ưu nét vẽ thông minh (Grid)")
        self.sw_smart_order.setChecked(True)
        layout.addWidget(self.sw_smart_order)
        
        self.sw_slide_transition = QCheckBox("Hiệu ứng cuộn trang khi chuyển cảnh")
        self.sw_slide_transition.setChecked(True)
        layout.addWidget(self.sw_slide_transition)
        
        # Separator line
        sep_logo = QFrame()
        sep_logo.setFrameShape(QFrame.HLine)
        sep_logo.setFrameShadow(QFrame.Sunken)
        sep_logo.setStyleSheet("background-color: #27272a; height: 1px; border: none; margin-top: 5px; margin-bottom: 5px;")
        layout.addWidget(sep_logo)
        
        # Logo management header
        self.lbl_logo_title = QLabel()
        self.lbl_logo_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_logo_title)
        
        self.cmb_logos = QComboBox()
        layout.addWidget(self.cmb_logos)
        
        # Logo actions layout
        logo_btns = QHBoxLayout()
        logo_btns.setSpacing(6)
        
        self.btn_logo_upload = QPushButton()
        self.btn_logo_upload.clicked.connect(self.upload_logo)
        logo_btns.addWidget(self.btn_logo_upload)
        
        self.btn_logo_pos = QPushButton()
        self.btn_logo_pos.clicked.connect(self.position_logo)
        logo_btns.addWidget(self.btn_logo_pos)
        
        self.btn_logo_del = QPushButton()
        self.btn_logo_del.clicked.connect(self.delete_logo)
        logo_btns.addWidget(self.btn_logo_del)
        
        layout.addLayout(logo_btns)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Nhạc & Cam")

    def _build_tab_export(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        hbox_opts = QHBoxLayout()
        vbox_res = QVBoxLayout()
        self.lbl_res_hdr = QLabel("Độ phân giải:")
        vbox_res.addWidget(self.lbl_res_hdr)
        self.cmb_res = QComboBox()
        self.cmb_res.addItems(["1920x1080 (16:9)", "1280x720 (16:9)", "1080x1080 (1:1)", "1080x1920 (9:16)"])
        self.cmb_res.setCurrentText("1920x1080 (16:9)")
        vbox_res.addWidget(self.cmb_res)
        hbox_opts.addLayout(vbox_res)
        
        vbox_fps = QVBoxLayout()
        self.lbl_fps_hdr = QLabel("Khung hình (FPS):")
        vbox_fps.addWidget(self.lbl_fps_hdr)
        self.cmb_fps = QComboBox()
        self.cmb_fps.addItems(["30 FPS", "60 FPS", "24 FPS"])
        self.cmb_fps.setCurrentText("30 FPS")
        vbox_fps.addWidget(self.cmb_fps)
        hbox_opts.addLayout(vbox_fps)
        layout.addLayout(hbox_opts)
        
        self.lbl_export_hdr = QLabel("Thư mục xuất video:")
        layout.addWidget(self.lbl_export_hdr)
        
        hbox_exp = QHBoxLayout()
        self.entry_export = QTextEdit()
        self.entry_export.setMaximumHeight(28)
        self.entry_export.setLineWrapMode(QTextEdit.NoWrap)
        self.entry_export.setPlainText(self.dirs["output"])
        hbox_exp.addWidget(self.entry_export)
        self.btn_choose_export = QPushButton("Chọn")
        self.btn_choose_export.clicked.connect(self._select_export_dir)
        hbox_exp.addWidget(self.btn_choose_export)
        layout.addLayout(hbox_exp)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Xuất Video")

    def _select_pen_color(self) -> None:
        cur_qcolor = QColor(self.pen_color_rgb[0], self.pen_color_rgb[1], self.pen_color_rgb[2])
        color = QColorDialog.getColor(cur_qcolor, self, "Chọn Màu Nét Vẽ" if self.current_lang == "vi" else "Select Stroke Color")
        if color.isValid():
            self.pen_color_rgb = [color.red(), color.green(), color.blue()]
            self.frame_color_prev.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); border: 1px solid white; border-radius: 4px;")
            self.refresh_canvas_preview()

    def _select_bg_music(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn Nhạc Nền" if self.current_lang == "vi" else "Select Background Music", "", "Audio Files (*.mp3 *.wav *.m4a *.ogg)")
        if file_path:
            self.entry_bgm.setPlainText(file_path)

    def _select_export_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục Xuất Video" if self.current_lang == "vi" else "Select Export Directory", self.entry_export.toPlainText())
        if dir_path:
            self.entry_export.setPlainText(dir_path)

    def update_language(self, lang: str) -> None:
        self.current_lang = lang
        t = TRANSLATIONS[lang]
        
        bg_translations = {
            "vi": {
                "Whiteboard": "Bảng trắng",
                "Blackboard": "Bảng đen",
                "Old Paper": "Giấy cũ",
                "Canvas": "Vải Canvas",
                "Paper Texture": "Vân giấy"
            },
            "en": {
                "Whiteboard": "Whiteboard",
                "Blackboard": "Blackboard",
                "Old Paper": "Old Paper",
                "Canvas": "Canvas",
                "Paper Texture": "Paper Texture"
            }
        }
        for i in range(self.cmb_bg.count()):
            data = self.cmb_bg.itemData(i)
            for key in bg_translations["en"]:
                if data == key:
                    self.cmb_bg.setItemText(i, bg_translations[lang][key])
                    break
        
        self.lbl_brand.setText(t["brand"])
        self.tabs.setTabText(0, t["tab_tts"])
        self.tabs.setTabText(1, t["tab_style"])
        self.tabs.setTabText(2, t["tab_audio"])
        self.tabs.setTabText(3, t["tab_export"])
        
        # Translate placeholder of script input box
        self.single_txt_script.setPlaceholderText("Nhập kịch bản thuyết minh tại đây..." if lang == "vi" else "Enter narration script here...")
        # Translate BGM input box placeholder
        self.entry_bgm.setPlaceholderText("Đường dẫn file MP3..." if lang == "vi" else "MP3 file path...")
        # Translate Choose Image button tooltip & text
        self.single_img_prev.setToolTip("Chọn hình ảnh đầu vào" if lang == "vi" else "Select input image")
        if not self.single_image_path:
            self.single_img_prev.setText("+ Chọn Ảnh" if lang == "vi" else "+ Choose Image")
        
        # Action buttons
        self.btn_render.setText(t["render_btn"])
        self.btn_pause.setText(t["pause_btn"])
        self.btn_resume.setText(t["resume_btn"])
        self.btn_cancel.setText(t["cancel_btn"])
        
        # Workspace titles
        self.lbl_preview_title.setText(t["preview_title"])
        self.lbl_log_title.setText(t["log_title"])
        
        # Labels inside tabs
        self.lbl_tts_model.setText(t["opt_tts_model"])
        self.lbl_voice_hdr.setText(t["opt_voice"])
        self.lbl_rate_hdr.setText(t["opt_rate"])
        self.lbl_pitch_hdr.setText(t["opt_pitch"])
        
        self.lbl_pen_hdr.setText(t["opt_pen"])
        self.lbl_bg_hdr.setText(t["opt_bg"])
        self.lbl_color_hdr.setText(t["opt_color"])
        self.lbl_width_hdr.setText(t["opt_width"])
        self.lbl_colormode_hdr.setText(t["opt_color_mode"])
        
        self.lbl_bgm_hdr.setText(t["opt_bgm"])
        self.lbl_vvol_hdr.setText(t["opt_volume_voice"])
        self.lbl_mvol_hdr.setText(t["opt_volume_voice_read"])
        self.lbl_color_style_hdr.setText(t["opt_color_style"])
        self.sw_camera.setText(t["opt_cam"])
        self.sw_smart_order.setText(t["opt_smart_grid"])
        self.sw_slide_transition.setText(t["opt_slide"])
        
        self.lbl_res_hdr.setText(t["opt_resolution"])
        self.lbl_fps_hdr.setText(t["opt_fps"])
        self.lbl_export_hdr.setText(t["opt_export_dir"])
        self.btn_choose_export.setText(t["opt_choose"])
        self.btn_bgm_browse.setText(t["opt_choose"])
        self.btn_color_pick.setText(t["opt_choose"])
        
        # Repopulate coloring style dropdown while keeping current choice
        current_data = self.cmb_color_style.currentData() or "gradual"
        self.cmb_color_style.clear()
        for text, code in COLOR_STYLES_MAP[lang]:
            self.cmb_color_style.addItem(text, code)
        idx = self.cmb_color_style.findData(current_data)
        if idx >= 0:
            self.cmb_color_style.setCurrentIndex(idx)
            
        self.lbl_single_title.setText(t["single_title"])
        self.lbl_single_image.setText(t["single_image_label"])
        self.lbl_single_script.setText(t["single_script_label"])
        self.btn_single_choose.setText(t["opt_choose"])
        if not self.single_image_path:
            self.lbl_single_filename.setText(t["single_no_image"])
            
        self.btn_load_proj.setText(t["open_proj"])
        self.btn_save_proj.setText(t["save_proj"])
        self.lbl_logo_title.setText(t["logo_title"])
        self.btn_logo_upload.setText(t["logo_upload"])
        self.btn_logo_pos.setText(t["logo_pos"])
        self.btn_logo_del.setText(t["logo_del"])
        self.update_logo_combobox()

    def update_voice_combobox(self) -> None:
        model = self.cmb_tts_model.currentText()
        voices = self.edge_voices if model == "Edge-TTS" else self.capcut_voices
        
        current_voice = self.cmb_voice.currentText()
        self.cmb_voice.clear()
        
        if not voices:
            self.cmb_voice.addItem("Đang tải danh sách giọng đọc..." if self.current_lang == "vi" else "Loading voice list...")
            return
            
        friendly_names = [v["FriendlyName"] for v in voices]
        self.cmb_voice.addItems(friendly_names)
        
        if current_voice in friendly_names:
            self.cmb_voice.setCurrentText(current_voice)
        elif friendly_names:
            if model == "Edge-TTS":
                default_voice = next((v["FriendlyName"] for v in voices if "HoaiMy" in v["Name"]), friendly_names[0])
            else:
                default_voice = next((v["FriendlyName"] for v in voices if "Nhỏ Ngọt Ngào" in v["Name"]), friendly_names[0])
            self.cmb_voice.setCurrentText(default_voice)

    def set_voices(self, edge_voices: List[Dict[str, Any]], capcut_voices: List[Dict[str, Any]]) -> None:
        self.edge_voices = edge_voices
        self.capcut_voices = capcut_voices
        self.update_voice_combobox()

    def delete_custom_brush(self) -> None:
        idx = self.cmb_pen.currentIndex()
        if idx < 0:
            return
            
        file_path = self.cmb_pen.itemData(idx)
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(
                self,
                "Cảnh báo" if self.current_lang == "vi" else "Warning",
                "Không thể xóa cọ vẽ mặc định." if self.current_lang == "vi" else "Cannot delete default brush styles."
            )
            return
            
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa" if self.current_lang == "vi" else "Confirm Delete",
            f"Bạn có chắc chắn muốn xóa cọ vẽ này khỏi hệ thống?" if self.current_lang == "vi" else "Are you sure you want to delete this custom brush?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        try:
            from drawing.brush import Brush
            if hasattr(Brush, "_custom_brush_cache") and file_path in Brush._custom_brush_cache:
                del Brush._custom_brush_cache[file_path]
                
            os.remove(file_path)
            self.cmb_pen.removeItem(idx)
            self.cmb_pen.setCurrentIndex(1)
            self.refresh_canvas_preview()
            
            QMessageBox.information(
                self,
                "Thành công" if self.current_lang == "vi" else "Success",
                "Đã xóa cọ vẽ tùy chỉnh." if self.current_lang == "vi" else "Deleted custom brush."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi" if self.current_lang == "vi" else "Error",
                f"Lỗi khi xóa: {str(e)}" if self.current_lang == "vi" else f"Failed to delete: {str(e)}"
            )

    def delete_custom_background(self) -> None:
        idx = self.cmb_bg.currentIndex()
        if idx < 0:
            return
            
        file_path = self.cmb_bg.itemData(idx)
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(
                self,
                "Cảnh báo" if self.current_lang == "vi" else "Warning",
                "Không thể xóa nền giấy mặc định." if self.current_lang == "vi" else "Cannot delete default background styles."
            )
            return
            
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa" if self.current_lang == "vi" else "Confirm Delete",
            f"Bạn có chắc chắn muốn xóa nền giấy này khỏi hệ thống?" if self.current_lang == "vi" else "Are you sure you want to delete this custom background?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        try:
            os.remove(file_path)
            self.cmb_bg.removeItem(idx)
            self.cmb_bg.setCurrentIndex(0)
            self.refresh_canvas_preview()
            
            QMessageBox.information(
                self,
                "Thành công" if self.current_lang == "vi" else "Success",
                "Đã xóa nền giấy tùy chỉnh." if self.current_lang == "vi" else "Deleted custom background."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi" if self.current_lang == "vi" else "Error",
                f"Lỗi khi xóa: {str(e)}" if self.current_lang == "vi" else f"Failed to delete: {str(e)}"
            )

    def update_delete_buttons_state(self) -> None:
        pass

    def refresh_canvas_preview(self) -> None:
        if not self.btn_render.isEnabled():
            return
            
        try:
            from drawing.renderer import DrawingRenderer
            from drawing.brush import Brush
            from PIL import Image, ImageDraw
            import math
            
            pen_style = self.cmb_pen.currentData() or self.cmb_pen.currentText()
            bg_style = self.cmb_bg.currentData() or self.cmb_bg.currentText()
            pen_width = self.sld_width.value() / 10.0
            
            res = (960, 540)
            renderer = DrawingRenderer(
                resolution=res,
                bg_style=bg_style,
                pen_style=pen_style,
                pen_color=tuple(self.pen_color_rgb),
                pen_width=pen_width,
                pen_opacity=1.0,
                hand_img_path=os.path.join(self.dirs["assets"], "hand.png"),
                camera_enabled=False
            )
            
            preview_img = renderer.bg_template.copy()
            draw = ImageDraw.Draw(preview_img)
            
            pts = []
            for x in range(250, 710, 5):
                y = 270 + int(70 * math.sin((x - 250) * (2 * math.pi / 300.0)))
                pts.append((float(x), float(y)))
                
            for i in range(len(pts) - 1):
                Brush.draw_segment(
                    draw,
                    pts[i],
                    pts[i+1],
                    style=pen_style,
                    color=tuple(self.pen_color_rgb),
                    base_width=pen_width,
                    opacity=1.0
                )
                
            if renderer.hand_img is not None:
                hand_w = int(128 * (res[0] / 1920.0) * 1.5)
                hand_h = int(128 * (res[1] / 1080.0) * 1.5)
                hand_resized = renderer.hand_img.resize((hand_w, hand_h), Image.Resampling.LANCZOS)
                
                end_x, end_y = pts[-1]
                dx = pts[-1][0] - pts[-2][0]
                dy = pts[-1][1] - pts[-2][1]
                angle_rad = math.atan2(dy, dx)
                angle_deg = math.degrees(angle_rad)
                
                rotated_hand = hand_resized.rotate(-angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
                
                rad = -angle_rad
                c_x = hand_w / 2
                c_y = hand_h / 2
                tx_orig = -c_x
                ty_orig = c_y
                
                tx_rot = tx_orig * math.cos(rad) - ty_orig * math.sin(rad)
                ty_rot = tx_orig * math.sin(rad) + ty_orig * math.cos(rad)
                
                rot_w, rot_h = rotated_hand.size
                rot_cx = rot_w / 2
                rot_cy = rot_h / 2
                
                paste_x = int(end_x - (rot_cx + tx_rot))
                paste_y = int(end_y - (rot_cy + ty_rot))
                
                preview_img.paste(rotated_hand, (paste_x, paste_y), rotated_hand)
                
            self.preview_canvas.set_image(preview_img)
            
        except Exception as e:
            import logging
            logger = logging.getLogger("AIDrawingVideo")
            logger.error(f"Failed to render style preview: {e}")

    def load_existing_custom_assets(self) -> None:
        brush_dir = os.path.join(self.dirs["assets"], "brushes")
        if os.path.exists(brush_dir):
            for f in os.listdir(brush_dir):
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    full_path = os.path.join(brush_dir, f)
                    exists = False
                    for i in range(self.cmb_pen.count()):
                        if self.cmb_pen.itemData(i) == full_path:
                            exists = True
                            break
                    if not exists:
                        self.cmb_pen.addItem(f, full_path)
                    
        bg_dir = os.path.join(self.dirs["assets"], "backgrounds")
        if os.path.exists(bg_dir):
            for f in os.listdir(bg_dir):
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    full_path = os.path.join(bg_dir, f)
                    exists = False
                    for i in range(self.cmb_bg.count()):
                        if self.cmb_bg.itemData(i) == full_path:
                            exists = True
                            break
                    if not exists:
                        self.cmb_bg.addItem(f, full_path)

    def upload_custom_brush(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Chọn cọ vẽ tùy chỉnh" if self.current_lang == "vi" else "Select Custom Brush", 
            "", 
            "Images (*.png *.jpg *.jpeg)"
        )
        if not file_path:
            return
            
        filename = os.path.basename(file_path)
        dest_dir = os.path.join(self.dirs["assets"], "brushes")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)
        
        try:
            import shutil
            shutil.copy(file_path, dest_path)
            
            exists = False
            for i in range(self.cmb_pen.count()):
                if self.cmb_pen.itemData(i) == dest_path:
                    exists = True
                    self.cmb_pen.setCurrentIndex(i)
                    break
            if not exists:
                self.cmb_pen.addItem(filename, dest_path)
                self.cmb_pen.setCurrentIndex(self.cmb_pen.count() - 1)
                
            QMessageBox.information(
                self, 
                "Thành công" if self.current_lang == "vi" else "Success",
                f"Đã tải lên cọ vẽ: {filename}" if self.current_lang == "vi" else f"Uploaded brush: {filename}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Lỗi" if self.current_lang == "vi" else "Error",
                f"Lỗi khi lưu cọ vẽ: {str(e)}" if self.current_lang == "vi" else f"Failed to save brush: {str(e)}"
            )

    def upload_custom_background(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Chọn nền giấy tùy chỉnh" if self.current_lang == "vi" else "Select Custom Background", 
            "", 
            "Images (*.png *.jpg *.jpeg)"
        )
        if not file_path:
            return
            
        filename = os.path.basename(file_path)
        dest_dir = os.path.join(self.dirs["assets"], "backgrounds")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)
        
        try:
            import shutil
            shutil.copy(file_path, dest_path)
            
            exists = False
            for i in range(self.cmb_bg.count()):
                if self.cmb_bg.itemData(i) == dest_path:
                    exists = True
                    self.cmb_bg.setCurrentIndex(i)
                    break
            if not exists:
                self.cmb_bg.addItem(filename, dest_path)
                self.cmb_bg.setCurrentIndex(self.cmb_bg.count() - 1)
                
            QMessageBox.information(
                self, 
                "Thành công" if self.current_lang == "vi" else "Success",
                f"Đã tải lên nền giấy: {filename}" if self.current_lang == "vi" else f"Uploaded background: {filename}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Lỗi" if self.current_lang == "vi" else "Error",
                f"Lỗi khi lưu nền giấy: {str(e)}" if self.current_lang == "vi" else f"Failed to save background: {str(e)}"
            )

    def append_log(self, log_line: str) -> None:
        self.txt_logs.appendPlainText(log_line)

    def update_progress(self, fraction: float, status_text: str) -> None:
        self.progress_bar.setValue(int(fraction * 100))
        self.lbl_progress.setText(status_text)

    def update_preview(self, img) -> None:
        self.preview_canvas.set_image(img)

    def lock_controls(self) -> None:
        self.btn_render.setEnabled(False)
        self.btn_render.setText("ĐANG XỬ LÝ..." if self.current_lang == "vi" else "PROCESSING...")
        self.btn_load_proj.setEnabled(False)
        self.btn_save_proj.setEnabled(False)
        
        self.btn_pause.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        
        self.progress_bar.setValue(0)
        self.lbl_progress.setText("Đang chuẩn bị tiến trình..." if self.current_lang == "vi" else "Preparing...")

    def unlock_controls(self) -> None:
        t = TRANSLATIONS[self.current_lang]
        self.btn_render.setEnabled(True)
        self.btn_render.setText(t["render_btn"])
        self.btn_load_proj.setEnabled(True)
        self.btn_save_proj.setEnabled(True)
        
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        
        self.preview_canvas.clear()

    def get_settings(self) -> Dict[str, Any]:
        tts_model = self.cmb_tts_model.currentText()
        voices = self.edge_voices if tts_model == "Edge-TTS" else self.capcut_voices
        
        voice_short = "vi-VN-HoaiMyNeural" if tts_model == "Edge-TTS" else "BV421_vivn_streaming"
        selected_friendly = self.cmb_voice.currentText()
        for v in voices:
            if v["FriendlyName"] == selected_friendly:
                voice_short = v["ShortName"]
                break
                
        res_str = self.cmb_res.currentText().split(" ")[0]
        res_w, res_h = map(int, res_str.split("x"))
        fps_val = int(self.cmb_fps.currentText().split(" ")[0])
        
        scenes_data = []
        if self.single_image_path:
            scenes_data = [{
                "image_path": self.single_image_path,
                "script": self.single_txt_script.toPlainText().strip()
            }]
            
        return {
            "tts_model": tts_model,
            "voice": voice_short,
            "rate": int(self.sld_rate.value()),
            "pitch": int(self.sld_pitch.value()),
            "fps": fps_val,
            "resolution": [res_w, res_h],
            "pen_style": self.cmb_pen.currentData() or self.cmb_pen.currentText(),
            "pen_color": self.pen_color_rgb,
            "pen_width": self.sld_width.value() / 10.0,
            "pen_opacity": 1.0,
            "bg_style": self.cmb_bg.currentData() or self.cmb_bg.currentText(),
            "music_path": self.entry_bgm.toPlainText().strip(),
            "voice_volume": self.sld_vvol.value() / 100.0,
            "music_volume": self.sld_mvol.value() / 100.0,
            "fade_in": 2.0,
            "fade_out": 3.0,
            "camera_enabled": self.sw_camera.isChecked(),
            "spatial_grouping": self.sw_smart_order.isChecked(),
            "slide_transition": self.sw_slide_transition.isChecked(),
            "color_option": self.cmb_color_opt.currentText(),
            "color_style": self.cmb_color_style.currentData() or "gradual",
            "export_dir": self.entry_export.toPlainText().strip(),
            "scenes": scenes_data,
            "logos": self.logos_list
        }

    def save_project_dialog(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "Lưu Dự Án (.json)", "", "JSON Files (*.json)")
        if not file_path:
            return
            
        settings = self.get_settings()
        if ProjectManager.save_project(file_path, settings):
            QMessageBox.information(self, "Dự Án", "Dự án đã được lưu thành công!")
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể lưu tệp dự án.")

    def load_project_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Mở Dự Án (.json)", "", "JSON Files (*.json)")
        if not file_path:
            return
            
        settings = ProjectManager.load_project(file_path)
        
        tts_model = settings.get("tts_model", "Edge-TTS")
        self.cmb_tts_model.setCurrentText(tts_model)
        self.update_voice_combobox()
        
        voice_short = settings.get("voice", "vi-VN-HoaiMyNeural" if tts_model == "Edge-TTS" else "BV421_vivn_streaming")
        voices = self.edge_voices if tts_model == "Edge-TTS" else self.capcut_voices
        friendly = next((v["FriendlyName"] for v in voices if v["ShortName"] == voice_short), None)
        if friendly:
            self.cmb_voice.setCurrentText(friendly)
            
        self.sld_rate.setValue(settings.get("rate", 0))
        self.sld_pitch.setValue(settings.get("pitch", 0))
        
        res = settings.get("resolution", [1920, 1080])
        res_str_find = f"{res[0]}x{res[1]}"
        for i in range(self.cmb_res.count()):
            if res_str_find in self.cmb_res.itemText(i):
                self.cmb_res.setCurrentIndex(i)
                break
                
        fps_val = settings.get("fps", 30)
        self.cmb_fps.setCurrentText(f"{fps_val} FPS")
        
        pen_style = settings.get("pen_style", "Ink Pen")
        idx_pen = self.cmb_pen.findData(pen_style)
        if idx_pen >= 0:
            self.cmb_pen.setCurrentIndex(idx_pen)
        else:
            if os.path.exists(pen_style):
                self.cmb_pen.addItem(os.path.basename(pen_style), pen_style)
                self.cmb_pen.setCurrentIndex(self.cmb_pen.count() - 1)
            else:
                self.cmb_pen.setCurrentText(pen_style)
                
        bg_style = settings.get("bg_style", "Whiteboard")
        idx_bg = self.cmb_bg.findData(bg_style)
        if idx_bg >= 0:
            self.cmb_bg.setCurrentIndex(idx_bg)
        else:
            if os.path.exists(bg_style):
                self.cmb_bg.addItem(os.path.basename(bg_style), bg_style)
                self.cmb_bg.setCurrentIndex(self.cmb_bg.count() - 1)
            else:
                self.cmb_bg.setCurrentText(bg_style)
        
        self.pen_color_rgb = settings.get("pen_color", [0, 0, 0])
        self.frame_color_prev.setStyleSheet(f"background-color: rgb({self.pen_color_rgb[0]}, {self.pen_color_rgb[1]}, {self.pen_color_rgb[2]}); border: 1px solid white; border-radius: 4px;")
        
        self.sld_width.setValue(int(settings.get("pen_width", 4.0) * 10))
        self.cmb_color_opt.setCurrentText(settings.get("color_option", "Outline then Color"))
        self.entry_bgm.setPlainText(settings.get("music_path", ""))
        self.sld_vvol.setValue(int(settings.get("voice_volume", 1.0) * 100))
        self.sld_mvol.setValue(int(settings.get("music_volume", 0.15) * 100))
        
        self.sw_camera.setChecked(settings.get("camera_enabled", True))
        self.sw_smart_order.setChecked(settings.get("spatial_grouping", True))
        self.sw_slide_transition.setChecked(settings.get("slide_transition", True))
        
        color_style = settings.get("color_style", "gradual")
        idx_style = self.cmb_color_style.findData(color_style)
        if idx_style >= 0:
            self.cmb_color_style.setCurrentIndex(idx_style)
            
        self.entry_export.setPlainText(settings.get("export_dir", self.dirs["output"]))
        
        self.logos_list = settings.get("logos", [])
        self.update_logo_combobox()
        
        scenes = settings.get("scenes", [])
        if scenes:
            scene_data = scenes[0]
            img_path = scene_data.get("image_path", "")
            self.single_image_path = img_path
            if img_path:
                self.lbl_single_filename.setText(os.path.basename(img_path))
                self.lbl_single_filename.setStyleSheet("color: #007acc; font-weight: bold;")
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(QSize(156, 86), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.single_img_prev.setIcon(QIcon(scaled))
                    self.single_img_prev.setIconSize(scaled.size())
                    self.single_img_prev.setText("")
                    self.single_img_prev.setProperty("hasImage", "true")
                    self.single_img_prev.style().unpolish(self.single_img_prev)
                    self.single_img_prev.style().polish(self.single_img_prev)
            else:
                self.single_image_path = ""
                self.lbl_single_filename.setText("Chưa chọn hình ảnh nào" if self.current_lang == "vi" else "No image selected")
                self.lbl_single_filename.setStyleSheet("color: #a1a1aa; font-style: italic;")
                self.single_img_prev.setIcon(QIcon())
                self.single_img_prev.setText("+ Chọn Ảnh" if self.current_lang == "vi" else "+ Choose Image")
                self.single_img_prev.setProperty("hasImage", "false")
                self.single_img_prev.style().unpolish(self.single_img_prev)
                self.single_img_prev.style().polish(self.single_img_prev)
                
            self.single_txt_script.setPlainText(scene_data.get("script", ""))
        else:
            self.single_image_path = ""
            self.lbl_single_filename.setText("Chưa chọn hình ảnh nào" if self.current_lang == "vi" else "No image selected")
            self.lbl_single_filename.setStyleSheet("color: #a1a1aa; font-style: italic;")
            self.single_img_prev.setIcon(QIcon())
            self.single_img_prev.setText("+ Chọn Ảnh" if self.current_lang == "vi" else "+ Choose Image")
            self.single_img_prev.setProperty("hasImage", "false")
            self.single_img_prev.style().unpolish(self.single_img_prev)
            self.single_img_prev.style().polish(self.single_img_prev)
            self.single_txt_script.setPlainText("")
            
        QMessageBox.information(self, "Dự Án", "Dự án đã được tải thành công!")

    def update_logo_combobox(self) -> None:
        self.cmb_logos.clear()
        if not self.logos_list:
            self.cmb_logos.addItem("Chưa tải logo nào..." if self.current_lang == "vi" else "No logos uploaded...")
            self.btn_logo_pos.setEnabled(False)
            self.btn_logo_del.setEnabled(False)
            return
            
        self.btn_logo_pos.setEnabled(True)
        self.btn_logo_del.setEnabled(True)
        for i, logo in enumerate(self.logos_list):
            filename = os.path.basename(logo["path"])
            pct_x = int(logo["cx_pct"] * 100)
            pct_y = int(logo["cy_pct"] * 100)
            pct_scale = int(logo["scale_pct"] * 100)
            self.cmb_logos.addItem(f"{i+1}. {filename} ({pct_scale}% | x:{pct_x} y:{pct_y})")

    def upload_logo(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh Logo" if self.current_lang == "vi" else "Select Logo Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not file_path:
            return
            
        dest_dir = os.path.join(self.dirs["assets"], "logos")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, os.path.basename(file_path))
        
        try:
            import shutil
            shutil.copy(file_path, dest_path)
            
            new_logo = {
                "path": dest_path,
                "cx_pct": 0.5,
                "cy_pct": 0.5,
                "scale_pct": 0.15
            }
            self.logos_list.append(new_logo)
            self.update_logo_combobox()
            self.cmb_logos.setCurrentIndex(len(self.logos_list) - 1)
            
            QMessageBox.information(
                self,
                "Thành công" if self.current_lang == "vi" else "Success",
                "Đã tải lên logo thành công!" if self.current_lang == "vi" else "Logo uploaded successfully!"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi" if self.current_lang == "vi" else "Error",
                f"Lỗi khi tải logo: {str(e)}" if self.current_lang == "vi" else f"Failed to upload logo: {str(e)}"
            )

    def position_logo(self) -> None:
        idx = self.cmb_logos.currentIndex()
        if not self.logos_list:
            return
        if idx < 0 or idx >= len(self.logos_list):
            idx = 0
            
        res_str = self.cmb_res.currentText().split(" ")[0]
        try:
            res_w, res_h = map(int, res_str.split("x"))
            aspect_ratio = res_w / res_h
        except Exception:
            aspect_ratio = 16.0 / 9.0
            
        import copy
        logos_copy = copy.deepcopy(self.logos_list)
        
        dialog = LogoPositionDialog(
            logos_copy,
            idx,
            aspect_ratio,
            lang=self.current_lang,
            theme=self.current_theme,
            parent=self
        )
        if dialog.exec():
            self.logos_list = dialog.get_values()
            self.update_logo_combobox()
            if idx < len(self.logos_list):
                self.cmb_logos.setCurrentIndex(idx)

    def delete_logo(self) -> None:
        idx = self.cmb_logos.currentIndex()
        if idx < 0 or idx >= len(self.logos_list):
            return
            
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa" if self.current_lang == "vi" else "Confirm Delete",
            "Bạn có chắc chắn muốn xóa logo này không?" if self.current_lang == "vi" else "Are you sure you want to delete this logo?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.logos_list.pop(idx)
            self.update_logo_combobox()

