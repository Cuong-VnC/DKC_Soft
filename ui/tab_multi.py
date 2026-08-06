import os
from typing import Dict, Any, List, Optional, Callable, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QSlider, QCheckBox, QProgressBar, QPlainTextEdit,
    QScrollArea, QFrame, QColorDialog, QFileDialog, QSplitter, QSizePolicy,
    QMessageBox, QTabWidget, QStyle, QApplication, QRadioButton, QDoubleSpinBox,
    QLineEdit
)
from PySide6.QtCore import Qt, QSize, QMimeData
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QDrag

from ui.preview_canvas import PreviewCanvas
from ui.config import TRANSLATIONS, COLOR_STYLES_MAP, COLOR_OPTIONS_MAP, DRAW_DIRECTIONS_MAP
from engine.project import ProjectManager
from ui.logo_dialog import LogoPositionDialog

def parse_timestamp_to_seconds(ts_str: str) -> float:
    # Example format: "00:00:01,234 --> 00:00:04,567"
    try:
        parts = ts_str.split("-->")
        if len(parts) == 2:
            start_str = parts[0].strip().replace(",", ".")
            end_str = parts[1].strip().replace(",", ".")
            
            def to_sec(time_str):
                # hh:mm:ss.ms
                h, m, s = time_str.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
                
            return to_sec(end_str) - to_sec(start_str)
    except Exception:
        pass
    return 8.0 # default fallback


class HoverThumbnailButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.original_pixmap = None
        self.hovered = False
        self.current_lang = "vi"
        
    def update_language(self, lang: str):
        self.current_lang = lang
        self.update_appearance()
        
    def set_thumbnail(self, pixmap: QPixmap):
        self.original_pixmap = pixmap
        self.update_appearance()
        
    def enterEvent(self, event):
        self.hovered = True
        self.update_appearance()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.hovered = False
        self.update_appearance()
        super().leaveEvent(event)
        
    def update_appearance(self):
        if self.original_pixmap and not self.original_pixmap.isNull():
            self.setIconSize(self.original_pixmap.size())
            if self.hovered:
                # 1. Fade the original pixmap: draw it with 0.4 opacity
                faded = QPixmap(self.original_pixmap.size())
                faded.fill(Qt.transparent)
                painter = QPainter(faded)
                painter.setOpacity(0.4)
                painter.drawPixmap(0, 0, self.original_pixmap)
                
                # 2. Draw replacement icon in the center
                painter.setOpacity(1.0)
                style_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
                icon_size = 24
                x_ic = (faded.width() - icon_size) // 2
                y_ic = (faded.height() - icon_size) // 2
                style_icon.paint(painter, x_ic, y_ic, icon_size, icon_size)
                
                # Draw "Thay thế" / "Replace" text at the bottom
                painter.setPen(QColor("#ffffff"))
                font = painter.font()
                font.setPixelSize(10)
                font.setBold(True)
                painter.setFont(font)
                replace_text = "Thay thế" if self.current_lang == "vi" else "Replace"
                painter.drawText(0, faded.height() - 14, faded.width(), 14, Qt.AlignCenter, replace_text)
                
                painter.end()
                self.setIcon(QIcon(faded))
                self.setText("")
            else:
                self.setIcon(QIcon(self.original_pixmap))
                self.setText("")
        else:
            self.setIcon(QIcon())
            self.setText("Chọn Ảnh" if self.current_lang == "vi" else "Select Image")

class StoryboardWidget(QWidget):
    def __init__(self, parent_tab, parent=None):
        super().__init__(parent)
        self.parent_tab = parent_tab
        self.setAcceptDrops(True)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            
    def dragMoveEvent(self, event):
        event.acceptProposedAction()
        
    def dropEvent(self, event):
        if event.mimeData().hasText():
            try:
                source_idx = int(event.mimeData().text())
                drop_pos = event.position().toPoint()
                dest_idx = -1
                for idx, card in enumerate(self.parent_tab.scene_cards):
                    if card.geometry().contains(drop_pos):
                        dest_idx = idx
                        break
                if dest_idx == -1 and self.parent_tab.scene_cards:
                    last_card = self.parent_tab.scene_cards[-1]
                    if drop_pos.y() > last_card.geometry().bottom():
                        dest_idx = len(self.parent_tab.scene_cards) - 1
                if dest_idx != -1 and dest_idx != source_idx:
                    card_to_move = self.parent_tab.scene_cards.pop(source_idx)
                    self.parent_tab.scene_cards.insert(dest_idx, card_to_move)
                    self.parent_tab.update_scene_indices()
                    self.parent_tab.rebuild_grid()
                    event.acceptProposedAction()
            except Exception as e:
                print("Drop error:", e)

class PySceneRow(QFrame):
    """SaaS-style horizontal row representing a Scene in the Storyboard table."""
    def __init__(self, index: int, on_delete: Callable[[], None], current_lang: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SceneRowFrame")
        self.setFixedHeight(86)
        
        self.index = index
        self.on_delete_cb = on_delete
        self.current_lang = current_lang
        self.image_path: str = ""
        self.drag_start_position = None
        self.timestamp = ""
        
        self.init_ui()

    def init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # 1. Index Label (Acts as a Drag Handle)
        lbl_prefix = TRANSLATIONS[self.current_lang]["scene_label"]
        self.lbl_index = QLabel(f"{lbl_prefix}{self.index}")
        self.lbl_index.setStyleSheet("font-weight: bold; color: #007acc; font-size: 11px;")
        self.lbl_index.setFixedWidth(60)
        self.lbl_index.setAlignment(Qt.AlignCenter)
        self.lbl_index.setCursor(Qt.OpenHandCursor)
        self.lbl_index.setToolTip(
            "Kéo thả để thay đổi thứ tự cảnh" if self.current_lang == "vi" else "Drag and drop to reorder scene"
        )
        layout.addWidget(self.lbl_index)
        
        # 2. Image Preview button (clickable thumbnail)
        self.btn_thumbnail = HoverThumbnailButton("Chọn Ảnh")
        self.btn_thumbnail.setFixedSize(120, 68)
        self.btn_thumbnail.clicked.connect(self._select_image)
        layout.addWidget(self.btn_thumbnail)
        
        # 3. Script text editor and Timestamp row container (Vertical Layout)
        self.vbox_script = QVBoxLayout()
        self.vbox_script.setContentsMargins(0, 0, 0, 0)
        self.vbox_script.setSpacing(4)
        
        self.txt_script = QTextEdit()
        self.txt_script.setPlaceholderText(f"{lbl_prefix} script...")
        self.txt_script.setAcceptRichText(False)
        self.txt_script.setFixedHeight(68)
        self.vbox_script.addWidget(self.txt_script)
        
        # Read-only Timestamp row for Video + Voice mode
        self.lbl_timestamp_vv = QLabel("Timestamp:")
        self.lbl_timestamp_vv.setStyleSheet("font-size: 10px; color: #a1a1aa; font-weight: bold;")
        self.txt_timestamp_vv = QLineEdit()
        self.txt_timestamp_vv.setReadOnly(True)
        self.txt_timestamp_vv.setFixedHeight(24)
        self.txt_timestamp_vv.setStyleSheet("font-size: 11px; background-color: #121214; color: #a1a1aa; border: 1px solid #27272a; border-radius: 4px; padding: 2px;")
        
        self.row_timestamp_vv = QWidget()
        row_ts_vv_layout = QHBoxLayout(self.row_timestamp_vv)
        row_ts_vv_layout.setContentsMargins(0, 0, 0, 0)
        row_ts_vv_layout.setSpacing(6)
        row_ts_vv_layout.addWidget(self.lbl_timestamp_vv)
        row_ts_vv_layout.addWidget(self.txt_timestamp_vv)
        
        self.vbox_script.addWidget(self.row_timestamp_vv)
        self.row_timestamp_vv.hide()
        
        layout.addLayout(self.vbox_script)
        
        # 3.2 Time inputs container (Video-only mode)
        self.time_container = QWidget()
        self.time_container.setFixedHeight(68)
        time_layout = QHBoxLayout(self.time_container)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(10)
        
        # Drawing duration
        vbox_draw = QVBoxLayout()
        vbox_draw.setSpacing(2)
        vbox_draw.setContentsMargins(0, 0, 0, 0)
        self.lbl_draw_time = QLabel("Thời gian vẽ (giây)" if self.current_lang == "vi" else "Draw time (s)")
        self.lbl_draw_time.setStyleSheet("font-size: 10px; color: #a1a1aa; font-weight: bold;")
        self.spin_draw_time = QDoubleSpinBox()
        self.spin_draw_time.setRange(0.1, 1000.0)
        self.spin_draw_time.setValue(5.0)
        self.spin_draw_time.setDecimals(1)
        self.spin_draw_time.setFixedHeight(30)
        vbox_draw.addWidget(self.lbl_draw_time)
        vbox_draw.addWidget(self.spin_draw_time)
        time_layout.addLayout(vbox_draw)
        
        # Freeze duration
        vbox_hold = QVBoxLayout()
        vbox_hold.setSpacing(2)
        vbox_hold.setContentsMargins(0, 0, 0, 0)
        self.lbl_hold_time = QLabel("Thời gian giữ (giây)" if self.current_lang == "vi" else "Hold time (s)")
        self.lbl_hold_time.setStyleSheet("font-size: 10px; color: #a1a1aa; font-weight: bold;")
        self.spin_hold_time = QDoubleSpinBox()
        self.spin_hold_time.setRange(0.0, 1000.0)
        self.spin_hold_time.setValue(3.0)
        self.spin_hold_time.setDecimals(1)
        self.spin_hold_time.setFixedHeight(30)
        vbox_hold.addWidget(self.lbl_hold_time)
        vbox_hold.addWidget(self.spin_hold_time)
        time_layout.addLayout(vbox_hold)
        
        # Timestamp for Video-only mode
        self.vbox_timestamp_vo = QWidget()
        vbox_ts_vo_layout = QVBoxLayout(self.vbox_timestamp_vo)
        vbox_ts_vo_layout.setContentsMargins(0, 0, 0, 0)
        vbox_ts_vo_layout.setSpacing(2)
        
        self.lbl_timestamp_vo = QLabel("Timestamp:")
        self.lbl_timestamp_vo.setStyleSheet("font-size: 10px; color: #a1a1aa; font-weight: bold;")
        
        self.txt_timestamp_vo = QLineEdit()
        self.txt_timestamp_vo.setReadOnly(True)
        self.txt_timestamp_vo.setFixedWidth(160)
        self.txt_timestamp_vo.setFixedHeight(30)
        self.txt_timestamp_vo.setStyleSheet("font-size: 11px; background-color: #121214; color: #a1a1aa; border: 1px solid #27272a; border-radius: 4px; padding: 2px;")
        
        vbox_ts_vo_layout.addWidget(self.lbl_timestamp_vo)
        vbox_ts_vo_layout.addWidget(self.txt_timestamp_vo)
        
        time_layout.addWidget(self.vbox_timestamp_vo)
        self.vbox_timestamp_vo.hide()
        
        layout.addWidget(self.time_container)
        self.time_container.hide()
        
        # 3.5 Transition dropdown
        vbox_trans = QVBoxLayout()
        vbox_trans.setContentsMargins(0, 0, 0, 0)
        vbox_trans.setSpacing(2)
        
        self.lbl_trans = QLabel()
        self.lbl_trans.setStyleSheet("font-size: 10px; color: #a1a1aa; font-weight: bold;")
        vbox_trans.addWidget(self.lbl_trans)
        
        self.cmb_transition = QComboBox()
        self.cmb_transition.setFixedWidth(120)
        self.cmb_transition.setFixedHeight(30)
        vbox_trans.addWidget(self.cmb_transition)
        layout.addLayout(vbox_trans)
        
        # 4. Delete button
        self.btn_delete = QPushButton("x")
        self.btn_delete.setObjectName("MiniDeleteBtn")
        self.btn_delete.setFixedSize(28, 28)
        self.btn_delete.clicked.connect(self.on_delete_cb)
        layout.addWidget(self.btn_delete)
        
        self.update_language(self.current_lang)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not hasattr(self, 'drag_start_position') or self.drag_start_position is None:
            return
        if (event.position() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.index - 1))
        drag.setMimeData(mime_data)
        
        pixmap = self.grab()
        scaled_pixmap = pixmap.scaled(
            pixmap.width() * 0.8,
            pixmap.height() * 0.8,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        drag.setPixmap(scaled_pixmap)
        drag.setHotSpot(event.position().toPoint() * 0.8)
        
        drag.exec(Qt.MoveAction)
        super().mouseMoveEvent(event)

    def _select_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn Hình Ảnh" if self.current_lang == "vi" else "Select Image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if file_path:
            self.set_image(file_path)

    def set_image(self, path: str) -> None:
        self.image_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                QSize(118, 66),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.btn_thumbnail.set_thumbnail(scaled_pixmap)
        else:
            filename = os.path.basename(path)
            self.btn_thumbnail.original_pixmap = None
            self.btn_thumbnail.setText(filename)
            self.btn_thumbnail.setIcon(QIcon())
            self.btn_thumbnail.setStyleSheet("background-color: #1b4a25; border: 1px solid #218838; border-radius: 4px; color: white;")

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        if mode == "video_voice":
            self.txt_script.show()
            self.time_container.hide()
        else:
            self.txt_script.hide()
            self.time_container.show()
        self.update_timestamp_visibility()

    def set_timestamp(self, timestamp: str) -> None:
        self.timestamp = timestamp
        self.txt_timestamp_vv.setText(timestamp)
        self.txt_timestamp_vo.setText(timestamp)
        self.update_timestamp_visibility()

    def update_timestamp_visibility(self) -> None:
        has_ts = bool(self.timestamp)
        lang = self.current_lang
        
        if getattr(self, "mode", "video_voice") == "video_voice":
            if has_ts:
                self.txt_script.setFixedHeight(38)
                self.row_timestamp_vv.show()
                self.setFixedHeight(106)
            else:
                self.txt_script.setFixedHeight(68)
                self.row_timestamp_vv.hide()
                self.setFixedHeight(86)
            
            self.vbox_timestamp_vo.hide()
            self.lbl_hold_time.show()
            self.spin_hold_time.show()
            
            # Reset draw time label
            self.lbl_draw_time.setText("Thời gian vẽ (giây)" if lang == "vi" else "Draw time (s)")
        else:
            self.setFixedHeight(86)
            self.row_timestamp_vv.hide()
            if has_ts:
                self.lbl_hold_time.hide()
                self.spin_hold_time.hide()
                self.vbox_timestamp_vo.show()
                # Rename Draw time to Hold time spinner
                self.lbl_draw_time.setText("Thời gian giữ (giây)" if lang == "vi" else "Hold time (s)")
            else:
                self.lbl_hold_time.show()
                self.spin_hold_time.show()
                self.vbox_timestamp_vo.hide()
                # Reset draw time label
                self.lbl_draw_time.setText("Thời gian vẽ (giây)" if lang == "vi" else "Draw time (s)")

    def get_data(self) -> Dict[str, Any]:
        draw_time = self.spin_draw_time.value()
        hold_time = self.spin_hold_time.value()
        ts = getattr(self, "timestamp", "")
        if ts:
            total_dur = parse_timestamp_to_seconds(ts)
            # If timestamp is present, the spinner draw_time represents hold_time
            hold_time = draw_time
            draw_time = max(0.1, total_dur - hold_time)
            
        return {
            "image_path": self.image_path,
            "script": self.txt_script.toPlainText().strip(),
            "transition": self.cmb_transition.currentData() or "random",
            "draw_time": draw_time,
            "hold_time": hold_time,
            "timestamp": ts
        }

    def set_data(self, data: Dict[str, Any]) -> None:
        self.txt_script.setPlainText(data.get("script", ""))
        img = data.get("image_path", "")
        if img:
            self.set_image(img)
        trans = data.get("transition", "random")
        idx = self.cmb_transition.findData(trans)
        if idx >= 0:
            self.cmb_transition.setCurrentIndex(idx)
            
        has_ts = bool(data.get("timestamp", ""))
        if has_ts:
            self.spin_draw_time.setValue(data.get("hold_time", 0.0))
        else:
            self.spin_draw_time.setValue(data.get("draw_time", 5.0))
            self.spin_hold_time.setValue(data.get("hold_time", 3.0))
            
        self.set_timestamp(data.get("timestamp", ""))

    def update_language(self, lang: str) -> None:
        self.current_lang = lang
        t = TRANSLATIONS[lang]
        
        lbl_prefix = t["scene_label"]
        self.lbl_index.setText(f"{lbl_prefix}{self.index}")
        self.lbl_index.setToolTip(
            "Kéo thả để thay đổi thứ tự cảnh" if lang == "vi" else "Drag and drop to reorder scene"
        )
        self.txt_script.setPlaceholderText(f"{lbl_prefix} script...")
        self.lbl_trans.setText(t["transition"] + ":")
        
        # Keep selected transition code
        current_code = self.cmb_transition.currentData()
        if current_code is None:
            current_code = "random"
        self.cmb_transition.clear()
        
        if lang == "vi":
            self.cmb_transition.addItem("Không (Cut)", "none")
            self.cmb_transition.addItem("Ngẫu nhiên", "random")
            
            FFMPEG_TRANSITIONS = [
                ("Mờ dần", "fade"),
                ("Quét sang trái", "wipeleft"),
                ("Quét sang phải", "wiperight"),
                ("Quét lên", "wipeup"),
                ("Quét xuống", "wipedown"),
                ("Trượt sang trái", "slideleft"),
                ("Trượt sang phải", "slideright"),
                ("Trượt lên", "slideup"),
                ("Trượt xuống", "slidedown"),
                ("Cắt hình tròn", "circlecrop"),
                ("Cắt hình chữ nhật", "rectcrop"),
                ("Khoảng cách", "distance"),
                ("Mờ đen", "fadeblack"),
                ("Mờ trắng", "fadewhite"),
                ("Tỏa tròn", "radial"),
                ("Trượt mượt trái", "smoothleft"),
                ("Trượt mượt phải", "smoothright"),
                ("Trượt mượt lên", "smoothup"),
                ("Trượt mượt xuống", "smoothdown"),
                ("Mở hình tròn", "circleopen"),
                ("Đóng hình tròn", "circleclose"),
                ("Mở ngang", "horzopen"),
                ("Đóng ngang", "horzclose"),
                ("Mở dọc", "vertopen"),
                ("Đóng dọc", "vertclose"),
                ("Chéo trên trái", "diagtl"),
                ("Chéo trên phải", "diagtr"),
                ("Chéo dưới trái", "diagbl"),
                ("Chéo dưới phải", "diagbr"),
                ("Lát cắt ngang trái", "hlslice"),
                ("Lát cắt ngang phải", "hrslice"),
                ("Lát cắt dọc lên", "vuslice"),
                ("Lát cắt dọc xuống", "vdslice"),
                ("Hòa tan", "dissolve"),
                ("Điểm ảnh hóa", "pixelize"),
                ("Gió ngang trái", "hlwind"),
                ("Gió ngang phải", "hrwind"),
                ("Gió dọc lên", "vuwind"),
                ("Gió dọc xuống", "vdwind"),
                ("Làm mờ ngang", "hblur"),
                ("Mờ xám", "fadegrays"),
                ("Co ngang", "squeezeh"),
                ("Co dọc", "squeezev"),
                ("Phóng to", "zoomin"),
            ]
        else:
            self.cmb_transition.addItem("None (Cut)", "none")
            self.cmb_transition.addItem("Random", "random")
            
            FFMPEG_TRANSITIONS = [
                ("Fade", "fade"),
                ("Wipe Left", "wipeleft"),
                ("Wipe Right", "wiperight"),
                ("Wipe Up", "wipeup"),
                ("Wipe Down", "wipedown"),
                ("Slide Left", "slideleft"),
                ("Slide Right", "slideright"),
                ("Slide Up", "slideup"),
                ("Slide Down", "slidedown"),
                ("Circle Crop", "circlecrop"),
                ("Rect Crop", "rectcrop"),
                ("Distance", "distance"),
                ("Fade Black", "fadeblack"),
                ("Fade White", "fadewhite"),
                ("Radial", "radial"),
                ("Smooth Left", "smoothleft"),
                ("Smooth Right", "smoothright"),
                ("Smooth Up", "smoothup"),
                ("Smooth Down", "smoothdown"),
                ("Circle Open", "circleopen"),
                ("Circle Close", "circleclose"),
                ("Horiz Open", "horzopen"),
                ("Horiz Close", "horzclose"),
                ("Vert Open", "vertopen"),
                ("Vert Close", "vertclose"),
                ("Diag TL", "diagtl"),
                ("Diag TR", "diagtr"),
                ("Diag BL", "diagbl"),
                ("Diag BR", "diagbr"),
                ("HL Slice", "hlslice"),
                ("HR Slice", "hrslice"),
                ("VU Slice", "vuslice"),
                ("VD Slice", "vdslice"),
                ("Dissolve", "dissolve"),
                ("Pixelize", "pixelize"),
                ("HL Wind", "hlwind"),
                ("HR Wind", "hrwind"),
                ("VU Wind", "vuwind"),
                ("VD Wind", "vdwind"),
                ("H Blur", "hblur"),
                ("Fade Grays", "fadegrays"),
                ("Squeeze H", "squeezeh"),
                ("Squeeze V", "squeezev"),
                ("Zoom In", "zoomin"),
            ]
            
        for display_name, trans_code in FFMPEG_TRANSITIONS:
            self.cmb_transition.addItem(display_name, trans_code)
            
        idx = self.cmb_transition.findData(current_code)
        if idx >= 0:
            self.cmb_transition.setCurrentIndex(idx)
            
        if hasattr(self.btn_thumbnail, "update_language"):
            self.btn_thumbnail.update_language(lang)

        self.lbl_draw_time.setText("Thời gian vẽ (giây)" if lang == "vi" else "Draw time (s)")
        self.lbl_hold_time.setText("Thời gian giữ (giây)" if lang == "vi" else "Hold time (s)")
        self.update_timestamp_visibility()


class MultiVideoTab(QWidget):
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
        
        self.scene_cards: List[PySceneRow] = []
        self.pen_color_rgb = [0, 0, 0]
        self.logos_list: List[Dict[str, Any]] = []
        self.current_theme = "dark"
        self.mode = "video_voice"
        
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("MainSplitter")
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #27272a;
                width: 4px;
            }
            QSplitter::handle:hover {
                background-color: #007acc;
            }
        """)
        
        # 1. Left Sidebar Settings
        sidebar = self._build_settings_sidebar()
        self.splitter.addWidget(sidebar)
        
        # 2. Center Timeline workspace
        center_frame = QFrame()
        center_frame.setObjectName("CenterStoryboardFrame")
        center_layout = QVBoxLayout(center_frame)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(8)
        
        self.lbl_center_title = QLabel()
        self.lbl_center_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #a1a1aa;")
        center_layout.addWidget(self.lbl_center_title)
        
        self.storyboard_scroll = QScrollArea()
        self.storyboard_scroll.setStyleSheet("border: none;")
        self.storyboard_scroll.setWidgetResizable(True)
        self.storyboard_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.storyboard_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.storyboard_widget = StoryboardWidget(self)
        self.storyboard_widget.setObjectName("StoryboardWidget")
        self.storyboard_layout = QGridLayout(self.storyboard_widget)
        self.storyboard_layout.setContentsMargins(0, 0, 0, 0)
        self.storyboard_layout.setSpacing(8)
        self.storyboard_layout.setAlignment(Qt.AlignTop)
        self.storyboard_scroll.setWidget(self.storyboard_widget)
        center_layout.addWidget(self.storyboard_scroll)
        
        self.btn_add_card_placeholder = QPushButton()
        self.btn_add_card_placeholder.setObjectName("AddCardBtn")
        self.btn_add_card_placeholder.setFixedHeight(36)
        self.btn_add_card_placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_add_card_placeholder.clicked.connect(self.add_scene)
        
        self.splitter.addWidget(center_frame)
        
        # 3. Right Sidebar
        right_panel = self._build_right_panel()
        self.splitter.addWidget(right_panel)
        
        self.splitter.setSizes([320, 640, 320])
        layout.addWidget(self.splitter)
        
        self.update_language(self.current_lang)
        self.load_existing_custom_assets()
        self.update_delete_buttons_state()
        self.refresh_canvas_preview()
        self.add_scene_card()

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
        
        # Mode Selection
        mode_frame = QFrame()
        mode_frame.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 4px;")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(6, 6, 6, 6)
        mode_layout.setSpacing(12)
        
        self.rad_video_voice = QRadioButton("Video + Voice")
        self.rad_video_voice.setStyleSheet("font-weight: bold; color: #ffffff;")
        self.rad_video_voice.setChecked(True)
        self.rad_video_voice.toggled.connect(lambda: self.change_mode("video_voice") if self.rad_video_voice.isChecked() else None)
        mode_layout.addWidget(self.rad_video_voice)
        
        self.rad_video_only = QRadioButton("Video only")
        self.rad_video_only.setStyleSheet("font-weight: bold; color: #ffffff;")
        self.rad_video_only.toggled.connect(lambda: self.change_mode("video_only") if self.rad_video_only.isChecked() else None)
        mode_layout.addWidget(self.rad_video_only)
        
        sidebar_layout.addWidget(mode_frame)
        
        self.tabs = QTabWidget()
        
        self._build_tab_tts()
        self._build_tab_style()
        self._build_tab_audio()
        self._build_tab_export()
        
        sidebar_layout.addWidget(self.tabs)
        
        # Bulk upload buttons
        upload_frame = QFrame()
        upload_frame.setStyleSheet("background: transparent; border: none;")
        upload_layout = QVBoxLayout(upload_frame)
        upload_layout.setContentsMargins(0, 0, 0, 0)
        upload_layout.setSpacing(6)
        
        self.btn_upload_images = QPushButton()
        self.btn_upload_images.setObjectName("UploadImagesBtn")
        self.btn_upload_images.setFixedHeight(32)
        self.btn_upload_images.setStyleSheet("""
            QPushButton#UploadImagesBtn {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #10b981, stop:1 #059669);
                border: 1px solid #047857;
                border-radius: 6px;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton#UploadImagesBtn:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #34d399, stop:1 #10b981);
                border-color: #059669;
            }
            QPushButton#UploadImagesBtn:pressed {
                background-color: #047857;
            }
        """)
        self.btn_upload_images.clicked.connect(self.upload_multiple_images)
        upload_layout.addWidget(self.btn_upload_images)
        
        self.btn_upload_script = QPushButton()
        self.btn_upload_script.setObjectName("UploadScriptBtn")
        self.btn_upload_script.setFixedHeight(32)
        self.btn_upload_script.setStyleSheet("""
            QPushButton#UploadScriptBtn {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #0ea5e9, stop:1 #0284c7);
                border: 1px solid #0369a1;
                border-radius: 6px;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton#UploadScriptBtn:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #38bdf8, stop:1 #0ea5e9);
                border-color: #0284c7;
            }
            QPushButton#UploadScriptBtn:pressed {
                background-color: #0369a1;
            }
        """)
        self.btn_upload_script.clicked.connect(self.upload_script_file)
        upload_layout.addWidget(self.btn_upload_script)
        
        sidebar_layout.addWidget(upload_frame)
        
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

    def change_mode(self, mode: str) -> None:
        self.mode = mode
        if mode == "video_voice":
            self.tabs.setTabEnabled(0, True)
        else:
            self.tabs.setTabEnabled(0, False)
            
        for sc in self.scene_cards:
            sc.set_mode(mode)

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
        
        self.lbl_voice_hdr = QLabel()
        layout.addWidget(self.lbl_voice_hdr)
        
        self.cmb_voice = QComboBox()
        self.cmb_voice.addItem("Đang tải danh sách giọng đọc...")
        layout.addWidget(self.cmb_voice)
        
        hbox_rate = QHBoxLayout()
        self.lbl_rate_hdr = QLabel()
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
        self.lbl_pitch_hdr = QLabel()
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
        self.lbl_pen_hdr = QLabel()
        vbox_pen.addWidget(self.lbl_pen_hdr)
        
        hbox_pen_ctrl = QHBoxLayout()
        self.cmb_pen = QComboBox()
        self.cmb_pen.addItem("Pencil", "Pencil")
        self.cmb_pen.addItem("Ink Pen", "Ink Pen")
        self.cmb_pen.addItem("Marker", "Marker")
        self.cmb_pen.addItem("Brush", "Brush")
        
        brushes_dir = os.path.join(self.dirs["assets"], "brushes")
        self.cmb_pen.addItem("Cọ vẽ 1", os.path.join(brushes_dir, "hand-1.png"))
        self.cmb_pen.addItem("Cọ vẽ 2", os.path.join(brushes_dir, "hand-2.png"))
        self.cmb_pen.addItem("Cọ vẽ 3", os.path.join(brushes_dir, "hand-3.png"))
        
        self.cmb_pen.setCurrentIndex(1)
        hbox_pen_ctrl.addWidget(self.cmb_pen)
        
        vbox_pen.addLayout(hbox_pen_ctrl)
        layout.addLayout(vbox_pen)
        
        vbox_bg = QVBoxLayout()
        self.lbl_bg_hdr = QLabel()
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
        
        vbox_color = QVBoxLayout()
        self.lbl_color_hdr = QLabel()
        vbox_color.addWidget(self.lbl_color_hdr)
        color_row = QHBoxLayout()
        self.btn_color_pick = QPushButton()
        self.btn_color_pick.clicked.connect(self._select_pen_color)
        color_row.addWidget(self.btn_color_pick)
        self.frame_color_prev = QFrame()
        self.frame_color_prev.setFixedSize(18, 18)
        self.frame_color_prev.setStyleSheet("background-color: black; border: 1px solid white; border-radius: 3px;")
        color_row.addWidget(self.frame_color_prev)
        color_row.addStretch()
        vbox_color.addLayout(color_row)
        layout.addLayout(vbox_color)
        
        vbox_mode = QVBoxLayout()
        self.lbl_colormode_hdr = QLabel()
        vbox_mode.addWidget(self.lbl_colormode_hdr)
        self.cmb_color_opt = QComboBox()
        vbox_mode.addWidget(self.cmb_color_opt)
        layout.addLayout(vbox_mode)
        
        vbox_dir = QVBoxLayout()
        self.lbl_direction_hdr = QLabel()
        vbox_dir.addWidget(self.lbl_direction_hdr)
        self.cmb_direction = QComboBox()
        vbox_dir.addWidget(self.cmb_direction)
        layout.addLayout(vbox_dir)
        
        hbox_width = QHBoxLayout()
        self.lbl_width_hdr = QLabel()
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
        self.cmb_color_opt.currentIndexChanged.connect(self.refresh_canvas_preview)
        self.cmb_direction.currentIndexChanged.connect(self.refresh_canvas_preview)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Nét Vẽ")

    def _build_tab_audio(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        self.lbl_bgm_hdr = QLabel()
        layout.addWidget(self.lbl_bgm_hdr)
        
        hbox_music = QHBoxLayout()
        self.entry_bgm = QTextEdit()
        self.entry_bgm.setMaximumHeight(28)
        self.entry_bgm.setPlaceholderText("Đường dẫn file MP3...")
        self.entry_bgm.setLineWrapMode(QTextEdit.NoWrap)
        hbox_music.addWidget(self.entry_bgm)
        self.btn_bgm_browse = QPushButton()
        self.btn_bgm_browse.clicked.connect(self._select_bg_music)
        hbox_music.addWidget(self.btn_bgm_browse)
        layout.addLayout(hbox_music)
        
        vbox_mvol = QVBoxLayout()
        hbox_mvol_lbl = QHBoxLayout()
        self.lbl_vvol_hdr = QLabel()
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
        self.lbl_mvol_hdr = QLabel()
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
        
        self.lbl_color_style_hdr = QLabel()
        layout.addWidget(self.lbl_color_style_hdr)
        
        self.cmb_color_style = QComboBox()
        layout.addWidget(self.cmb_color_style)
        
        self.sw_camera = QCheckBox()
        self.sw_camera.setChecked(True)
        layout.addWidget(self.sw_camera)
        
        self.sw_smart_order = QCheckBox()
        self.sw_smart_order.setChecked(True)
        layout.addWidget(self.sw_smart_order)
        
        self.sw_slide_transition = QCheckBox()
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
        self.lbl_res_hdr = QLabel()
        vbox_res.addWidget(self.lbl_res_hdr)
        self.cmb_res = QComboBox()
        self.cmb_res.addItems(["1920x1080 (16:9)", "1280x720 (16:9)", "1080x1080 (1:1)", "1080x1920 (9:16)"])
        self.cmb_res.setCurrentText("1920x1080 (16:9)")
        vbox_res.addWidget(self.cmb_res)
        hbox_opts.addLayout(vbox_res)
        
        vbox_fps = QVBoxLayout()
        self.lbl_fps_hdr = QLabel()
        vbox_fps.addWidget(self.lbl_fps_hdr)
        self.cmb_fps = QComboBox()
        self.cmb_fps.addItems(["30 FPS", "60 FPS", "24 FPS"])
        self.cmb_fps.setCurrentText("30 FPS")
        vbox_fps.addWidget(self.cmb_fps)
        hbox_opts.addLayout(vbox_fps)
        layout.addLayout(hbox_opts)
        
        # Chế độ xuất video
        self.lbl_export_mode = QLabel()
        self.lbl_export_mode.setStyleSheet("font-weight: bold; margin-top: 4px;")
        layout.addWidget(self.lbl_export_mode)
        
        hbox_mode_opts = QHBoxLayout()
        self.rdo_export_merged = QRadioButton()
        self.rdo_export_merged.setStyleSheet("font-weight: bold; color: #ffffff;")
        self.rdo_export_merged.setChecked(True)
        hbox_mode_opts.addWidget(self.rdo_export_merged)
        
        self.rdo_export_scenes = QRadioButton()
        self.rdo_export_scenes.setStyleSheet("font-weight: bold; color: #ffffff;")
        hbox_mode_opts.addWidget(self.rdo_export_scenes)
        layout.addLayout(hbox_mode_opts)
        
        self.lbl_export_hdr = QLabel()
        layout.addWidget(self.lbl_export_hdr)
        
        hbox_exp = QHBoxLayout()
        self.entry_export = QTextEdit()
        self.entry_export.setMaximumHeight(28)
        self.entry_export.setLineWrapMode(QTextEdit.NoWrap)
        self.entry_export.setPlainText(self.dirs["output"])
        hbox_exp.addWidget(self.entry_export)
        self.btn_choose_export = QPushButton()
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

    def add_scene(self) -> None:
        self.add_scene_card()

    def add_scene_card(self, data: Optional[Dict[str, Any]] = None) -> PySceneRow:
        idx = len(self.scene_cards) + 1
        def delete_cmd():
            title = "Xác nhận xóa" if self.current_lang == "vi" else "Confirm Delete"
            question = f"Bạn có muốn xóa cảnh #{card.index} này không?" if self.current_lang == "vi" else f"Do you want to delete scene #{card.index}?"
            reply = QMessageBox.question(self, title, question, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove_scene(card)
        card = PySceneRow(
            idx,
            on_delete=delete_cmd,
            current_lang=self.current_lang
        )
        card.set_mode(self.mode)
        self.scene_cards.append(card)
        if data:
            card.set_data(data)
        self.rebuild_grid()
        self.storyboard_scroll.verticalScrollBar().setValue(self.storyboard_scroll.verticalScrollBar().maximum())
        return card

    def remove_scene(self, card: PySceneRow, rebuild: bool = True) -> None:
        self.scene_cards.remove(card)
        card.deleteLater()
        self.update_scene_indices()
        if rebuild:
            self.rebuild_grid()

    def update_scene_indices(self) -> None:
        for i, sc in enumerate(self.scene_cards):
            sc.index = i + 1
            sc.update_language(self.current_lang)

    def clear_all_scenes(self) -> None:
        for card in list(self.scene_cards):
            self.remove_scene(card, rebuild=False)
        self.rebuild_grid()

    def rebuild_grid(self) -> None:
        for card in self.scene_cards:
            self.storyboard_layout.removeWidget(card)
        self.storyboard_layout.removeWidget(self.btn_add_card_placeholder)
        for idx, card in enumerate(self.scene_cards):
            self.storyboard_layout.addWidget(card, idx, 0)
            card.show()
        placeholder_idx = len(self.scene_cards)
        self.storyboard_layout.addWidget(self.btn_add_card_placeholder, placeholder_idx, 0)
        self.btn_add_card_placeholder.show()

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
        self.lbl_direction_hdr.setText(t["opt_draw_direction"])
        
        self.lbl_bgm_hdr.setText(t["opt_bgm"])
        self.entry_bgm.setPlaceholderText("Đường dẫn file MP3..." if lang == "vi" else "MP3 file path...")
        self.lbl_vvol_hdr.setText(t["opt_volume_voice"])
        self.lbl_mvol_hdr.setText(t["opt_volume_voice_read"])
        self.lbl_color_style_hdr.setText(t["opt_color_style"])
        self.sw_camera.setText(t["opt_cam"])
        self.sw_smart_order.setText(t["opt_smart_grid"])
        self.sw_slide_transition.setText(t["opt_slide"])
        
        self.lbl_res_hdr.setText(t["opt_resolution"])
        self.lbl_fps_hdr.setText(t["opt_fps"])
        self.lbl_export_mode.setText(t.get("opt_export_mode", "Chế độ xuất video:"))
        self.rdo_export_merged.setText(t.get("opt_export_merged", "Video đã ghép"))
        self.rdo_export_scenes.setText(t.get("opt_export_scenes", "Video từng cảnh"))
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
            
        
        # Update cmb_color_opt
        current_opt_data = self.cmb_color_opt.currentData() or self.cmb_color_opt.currentText()
        eng_opt_key = current_opt_data
        for item_lang in ["vi", "en"]:
            for display_name, key in COLOR_OPTIONS_MAP[item_lang]:
                if current_opt_data == display_name or current_opt_data == key:
                    eng_opt_key = key
                    break
        self.cmb_color_opt.clear()
        for display_name, key in COLOR_OPTIONS_MAP[lang]:
            self.cmb_color_opt.addItem(display_name, key)
        idx_opt = self.cmb_color_opt.findData(eng_opt_key)
        if idx_opt >= 0:
            self.cmb_color_opt.setCurrentIndex(idx_opt)
        else:
            self.cmb_color_opt.setCurrentIndex(1) # Default
            
        # Update cmb_direction
        current_dir_data = self.cmb_direction.currentData() or self.cmb_direction.currentText()
        eng_dir_key = current_dir_data
        for item_lang in ["vi", "en"]:
            for display_name, key in DRAW_DIRECTIONS_MAP[item_lang]:
                if current_dir_data == display_name or current_dir_data == key:
                    eng_dir_key = key
                    break
        self.cmb_direction.clear()
        for display_name, key in DRAW_DIRECTIONS_MAP[lang]:
            self.cmb_direction.addItem(display_name, key)
        idx_dir = self.cmb_direction.findData(eng_dir_key)
        if idx_dir >= 0:
            self.cmb_direction.setCurrentIndex(idx_dir)
        else:
            self.cmb_direction.setCurrentIndex(0) # Default
            
        self.btn_load_proj.setText(t["open_proj"])
        self.btn_save_proj.setText(t["save_proj"])
        self.lbl_center_title.setText(t["storyboard_title"])
        self.btn_add_card_placeholder.setText(t["add_scene_btn"])
        
        # New translations
        self.btn_upload_images.setText("Tải lên nhiều ảnh (mỗi ảnh là 1 cảnh)" if lang == "vi" else "Upload Images (1 per scene)")
        self.btn_upload_script.setText("Tải lên Script (.txt, .srt)" if lang == "vi" else "Upload Script (.txt, .srt)")
        self.lbl_logo_title.setText(t["logo_title"])
        self.btn_logo_upload.setText(t["logo_upload"])
        self.btn_logo_pos.setText(t["logo_pos"])
        self.btn_logo_del.setText(t["logo_del"])
        self.update_logo_combobox()
        
        for sc in self.scene_cards:
            sc.update_language(lang)

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
            
            # Determine hand image path and actual pen style for preview
            hand_path = os.path.join(self.dirs["assets"], "hand.png")
            actual_pen_style = pen_style
            if os.path.exists(str(pen_style)):
                filename = os.path.basename(str(pen_style)).lower()
                if "hand-" in filename or filename.startswith("hand"):
                    hand_path = pen_style
                    actual_pen_style = "Ink Pen"
                else:
                    actual_pen_style = pen_style
            
            res = (960, 540)
            renderer = DrawingRenderer(
                resolution=res,
                bg_style=bg_style,
                pen_style=actual_pen_style,
                pen_color=tuple(self.pen_color_rgb),
                pen_width=pen_width,
                pen_opacity=1.0,
                hand_img_path=hand_path,
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
                    style=actual_pen_style,
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
        self.btn_add_card_placeholder.setEnabled(False)
        
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
        self.btn_add_card_placeholder.setEnabled(True)
        
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
        scenes_data = [sc.get_data() for sc in self.scene_cards]
        
        return {
            "mode": self.mode,
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
            "color_option": self.cmb_color_opt.currentData() or self.cmb_color_opt.currentText(),
            "draw_direction": self.cmb_direction.currentData() or self.cmb_direction.currentText(),
            "color_style": self.cmb_color_style.currentData() or "gradual",
            "export_mode": "merged" if self.rdo_export_merged.isChecked() else "scenes",
            "export_dir": self.entry_export.toPlainText().strip(),
            "scenes": scenes_data,
            "logos": self.logos_list
        }

    def load_project_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Mở Dự Án (.json)", "", "JSON Files (*.json)")
        if not file_path:
            return
            
        settings = ProjectManager.load_project(file_path)
        
        mode = settings.get("mode", "video_voice")
        if mode == "video_voice":
            self.rad_video_voice.setChecked(True)
        else:
            self.rad_video_only.setChecked(True)
        self.change_mode(mode)
        
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
        color_opt = settings.get("color_option", "Outline then Color")
        idx_color = self.cmb_color_opt.findData(color_opt)
        if idx_color >= 0:
            self.cmb_color_opt.setCurrentIndex(idx_color)
        else:
            idx_color_text = self.cmb_color_opt.findText(color_opt)
            if idx_color_text >= 0:
                self.cmb_color_opt.setCurrentIndex(idx_color_text)
            else:
                self.cmb_color_opt.setCurrentText(color_opt)
                
        draw_dir = settings.get("draw_direction", "left_to_right")
        idx_dir = self.cmb_direction.findData(draw_dir)
        if idx_dir >= 0:
            self.cmb_direction.setCurrentIndex(idx_dir)
        else:
            idx_dir_text = self.cmb_direction.findText(draw_dir)
            if idx_dir_text >= 0:
                self.cmb_direction.setCurrentIndex(idx_dir_text)
            else:
                self.cmb_direction.setCurrentText(draw_dir)
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
        
        export_mode = settings.get("export_mode", "merged")
        if export_mode == "scenes":
            self.rdo_export_scenes.setChecked(True)
        else:
            self.rdo_export_merged.setChecked(True)
        
        self.logos_list = settings.get("logos", [])
        self.update_logo_combobox()
        
        self.clear_all_scenes()
        for sc_data in settings.get("scenes", []):
            self.add_scene_card(sc_data)
            
        QMessageBox.information(self, "Dự Án", "Dự án đã được tải thành công!")

    def save_project_dialog(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "Lưu Dự Án (.json)", "", "JSON Files (*.json)")
        if not file_path:
            return
            
        settings = self.get_settings()
        if ProjectManager.save_project(file_path, settings):
            QMessageBox.information(self, "Dự Án", "Dự án đã được lưu thành công!")
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể lưu tệp dự án.")

    def upload_multiple_images(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Tải lên nhiều ảnh" if self.current_lang == "vi" else "Upload Multiple Images",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not file_paths:
            return
            
        title = "Ghép ảnh" if self.current_lang == "vi" else "Merge Images"
        question = "Bạn có muốn ghép các hình ảnh này vào các cảnh hiện có không? (Chọn 'No' sẽ xóa sạch cảnh hiện tại và tạo mới)" if self.current_lang == "vi" else "Do you want to merge these images into existing scenes? (Selecting 'No' will clear current scenes and create new ones)"
        reply = QMessageBox.question(self, title, question, QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
        
        if reply == QMessageBox.Cancel:
            return
            
        if reply == QMessageBox.No:
            self.clear_all_scenes()
            
        num_existing = len(self.scene_cards)
        for i, img in enumerate(file_paths):
            if i < num_existing:
                self.scene_cards[i].set_image(img)
            else:
                card = self.add_scene_card({"image_path": img, "script": "", "transition": "random", "timestamp": ""})
                card.set_mode(self.mode)

    def parse_srt_script(self, content: str) -> List[Dict[str, str]]:
        import re
        blocks = re.split(r'\n\s*\n', content.strip())
        results = []
        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if len(lines) >= 3:
                if '-->' in lines[1]:
                    timestamp = lines[1]
                    text = " ".join(lines[2:])
                    if text:
                        results.append({"script": text, "timestamp": timestamp})
                else:
                    time_line = ""
                    text_lines = []
                    for line in lines:
                        if '-->' in line:
                            time_line = line
                        elif not line.isdigit():
                            text_lines.append(line)
                    text = " ".join(text_lines)
                    if text:
                        results.append({"script": text, "timestamp": time_line})
            elif len(lines) == 2:
                if '-->' in lines[0]:
                    results.append({"script": lines[1], "timestamp": lines[0]})
            elif len(lines) == 1:
                line = lines[0]
                if not line.isdigit() and '-->' not in line:
                    results.append({"script": line, "timestamp": ""})
        return results

    def upload_script_file(self) -> None:
        script_path, _ = QFileDialog.getOpenFileName(
            self,
            "Tải lên file kịch bản (.txt, .srt)" if self.current_lang == "vi" else "Upload Script File (.txt, .srt)",
            "",
            "Script Files (*.txt *.srt)"
        )
        if not script_path:
            return
            
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                script_text = f.read()
        except UnicodeDecodeError:
            try:
                with open(script_path, "r", encoding="ansi") as f:
                    script_text = f.read()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi" if self.current_lang == "vi" else "Error", 
                                     f"Không thể đọc file: {str(e)}")
                return
        except Exception as e:
            QMessageBox.critical(self, "Lỗi" if self.current_lang == "vi" else "Error", 
                                 f"Không thể đọc file: {str(e)}")
            return
            
        results = []
        if script_path.lower().endswith(".srt"):
            results = self.parse_srt_script(script_text)
        else:
            raw_lines = script_text.split("\n")
            results = [{"script": line.strip(), "timestamp": ""} for line in raw_lines if line.strip()]
            
        title = "Ghép kịch bản" if self.current_lang == "vi" else "Merge Script"
        question = "Bạn có muốn ghép kịch bản này vào các cảnh hiện có không? (Chọn 'No' sẽ xóa sạch cảnh hiện tại và tạo mới)" if self.current_lang == "vi" else "Do you want to merge this script into existing scenes? (Selecting 'No' will clear current scenes and create new ones)"
        reply = QMessageBox.question(self, title, question, QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
        
        if reply == QMessageBox.Cancel:
            return
            
        if reply == QMessageBox.No:
            self.clear_all_scenes()
            
        num_existing = len(self.scene_cards)
        for i, item in enumerate(results):
            if i < num_existing:
                self.scene_cards[i].txt_script.setPlainText(item["script"])
                self.scene_cards[i].set_timestamp(item["timestamp"])
            else:
                card = self.add_scene_card({"image_path": "", "script": item["script"], "transition": "random", "timestamp": item["timestamp"]})
                card.set_mode(self.mode)

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

