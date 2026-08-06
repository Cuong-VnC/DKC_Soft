import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QWidget, QComboBox
from PySide6.QtCore import Qt, QPointF, QSize
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen

class LogoPositionWidget(QWidget):
    def __init__(self, logos: list, selected_index: int, aspect_ratio: float, lang: str = "vi", theme: str = "dark", parent=None):
        super().__init__(parent)
        self.logos = logos
        self.selected_index = selected_index
        self.aspect_ratio = aspect_ratio
        self.lang = lang
        self.theme = theme
        
        # Pre-load pixmaps
        self.logo_pixmaps = []
        for logo in self.logos:
            path = logo.get("path", "")
            if path and os.path.exists(path):
                self.logo_pixmaps.append(QPixmap(path))
            else:
                self.logo_pixmaps.append(QPixmap())
                
        self.dragging = False
        self.drag_offset = QPointF(0, 0)
        self.setMinimumSize(450, 350)
        
    def get_preview_rect(self) -> tuple:
        w_widget = self.width()
        h_widget = self.height()
        
        max_w = w_widget - 40
        max_h = h_widget - 40
        
        if max_w <= 0 or max_h <= 0:
            return 0, 0, w_widget, h_widget
            
        if max_w / max_h >= self.aspect_ratio:
            h_p = max_h
            w_p = int(max_h * self.aspect_ratio)
        else:
            w_p = max_w
            h_p = int(max_w / self.aspect_ratio)
            
        x_p = (w_widget - w_p) // 2
        y_p = (h_widget - h_p) // 2
        
        return x_p, y_p, w_p, h_p
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        x_p, y_p, w_p, h_p = self.get_preview_rect()
        # 1. Background
        bg_color = QColor("#f4f4f5") if self.theme == "light" else QColor("#121214")
        painter.fillRect(self.rect(), bg_color)
        
        # 2. Video area canvas
        painter.fillRect(x_p, y_p, w_p, h_p, QColor("#1e1e24"))
        
        # Draw canvas border
        pen = QPen(QColor("#007acc"), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(x_p, y_p, w_p, h_p)
        
        # Text label: big, bold, centered
        painter.setPen(QPen(QColor(113, 113, 122, 100), 2, Qt.SolidLine))
        font = painter.font()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        text_label = "Khung Hình Xuất Video" if self.lang == "vi" else "Video Export Frame"
        painter.drawText(x_p, y_p, w_p, h_p, Qt.AlignCenter, text_label)
        
        # 3. Draw Logos
        for idx, logo in enumerate(self.logos):
            pixmap = self.logo_pixmaps[idx]
            if pixmap.isNull():
                continue
                
            lw = int(w_p * logo["scale_pct"])
            lh = int(lw * pixmap.height() / pixmap.width())
            if lw > 0 and lh > 0:
                lx = int(x_p + w_p * logo["cx_pct"] - lw / 2)
                ly = int(y_p + h_p * logo["cy_pct"] - lh / 2)
                
                painter.drawPixmap(lx, ly, lw, lh, pixmap)
                
                # Selection outline
                if idx == self.selected_index:
                    painter.setPen(QPen(QColor("#00ff00"), 2, Qt.SolidLine))
                    painter.drawRect(lx, ly, lw, lh)
                    
                    # Draw a center indicator
                    painter.setBrush(QColor("#00ff00"))
                    painter.drawEllipse(QPointF(lx + lw/2, ly + lh/2), 3.0, 3.0)
                else:
                    painter.setPen(QPen(QColor("#a1a1aa"), 1, Qt.DashLine))
                    painter.drawRect(lx, ly, lw, lh)
                    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            x_p, y_p, w_p, h_p = self.get_preview_rect()
            if w_p <= 0 or h_p <= 0:
                return
                
            click_pos = event.position()
            
            # Find which logo was clicked, from top (end of list) to bottom (start)
            clicked_idx = -1
            for idx in reversed(range(len(self.logos))):
                logo = self.logos[idx]
                pixmap = self.logo_pixmaps[idx]
                if pixmap.isNull():
                    continue
                    
                lw = int(w_p * logo["scale_pct"])
                lh = int(lw * pixmap.height() / pixmap.width())
                lx = int(x_p + w_p * logo["cx_pct"] - lw / 2)
                ly = int(y_p + h_p * logo["cy_pct"] - lh / 2)
                
                if lx <= click_pos.x() <= lx + lw and ly <= click_pos.y() <= ly + lh:
                    clicked_idx = idx
                    break
                    
            if clicked_idx != -1:
                self.selected_index = clicked_idx
                if self.parent() and hasattr(self.parent(), "select_logo"):
                    self.parent().select_logo(clicked_idx)
                    
                # Set up drag
                logo = self.logos[clicked_idx]
                self.dragging = True
                self.drag_offset = QPointF(
                    click_pos.x() - (x_p + w_p * logo["cx_pct"]),
                    click_pos.y() - (y_p + h_p * logo["cy_pct"])
                )
                self.update()
                
    def mouseMoveEvent(self, event):
        if self.dragging and 0 <= self.selected_index < len(self.logos):
            x_p, y_p, w_p, h_p = self.get_preview_rect()
            if w_p <= 0 or h_p <= 0:
                return
                
            move_pos = event.position()
            logo = self.logos[self.selected_index]
            new_cx = move_pos.x() - self.drag_offset.x()
            new_cy = move_pos.y() - self.drag_offset.y()
            
            logo["cx_pct"] = (new_cx - x_p) / w_p
            logo["cy_pct"] = (new_cy - y_p) / h_p
            
            # Clamp percentage
            logo["cx_pct"] = max(0.0, min(1.0, logo["cx_pct"]))
            logo["cy_pct"] = max(0.0, min(1.0, logo["cy_pct"]))
            
            self.update()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False

class LogoPositionDialog(QDialog):
    def __init__(self, logos: list, selected_index: int, aspect_ratio: float, lang: str = "vi", theme: str = "dark", parent=None):
        super().__init__(parent)
        self.current_lang = lang
        self.current_theme = theme
        
        self.setWindowTitle("Chỉnh Vị Trí Logos" if lang == "vi" else "Adjust Logo Positions")
        self.resize(700, 620)
        
        bg_dialog = "#f4f4f5" if theme == "light" else "#18181b"
        color_text = "#18181b" if theme == "light" else "#e1e1e6"
        bg_combo = "#ffffff" if theme == "light" else "#09090b"
        border_combo = "#ccc" if theme == "light" else "#27272a"
        color_combo = "#18181b" if theme == "light" else "#ffffff"
        bg_btn = "#e4e4e7" if theme == "light" else "#27272a"
        border_btn = "#ccc" if theme == "light" else "#3f3f46"
        color_btn = "#18181b" if theme == "light" else "#ffffff"
        hover_btn = "#d4d4d8" if theme == "light" else "#3f3f46"
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_dialog};
            }}
            QLabel {{
                color: {color_text};
                font-weight: bold;
            }}
            QComboBox {{
                background-color: {bg_combo};
                border: 1px solid {border_combo};
                border-radius: 6px;
                padding: 6px 12px;
                color: {color_combo};
            }}
            QPushButton {{
                background-color: {bg_btn};
                border: 1px solid {border_btn};
                padding: 6px 14px;
                border-radius: 4px;
                color: {color_btn};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_btn};
            }}
            QPushButton#SaveBtn {{
                background-color: #007acc;
                border: 1px solid #0098ff;
                color: #ffffff;
            }}
            QPushButton#SaveBtn:hover {{
                background-color: #0098ff;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Active Logo selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Đang chỉnh sửa:" if lang == "vi" else "Editing:"))
        
        self.cmb_active = QComboBox()
        for idx, logo in enumerate(logos):
            filename = os.path.basename(logo["path"])
            self.cmb_active.addItem(f"{idx+1}. {filename}")
        if logos:
            self.cmb_active.setCurrentIndex(selected_index)
        self.cmb_active.currentIndexChanged.connect(self._on_logo_selection_changed)
        selector_layout.addWidget(self.cmb_active, stretch=1)
        layout.addLayout(selector_layout)
        
        # Preview Widget
        self.preview_widget = LogoPositionWidget(logos, selected_index, aspect_ratio, lang, theme, self)
        layout.addWidget(self.preview_widget, stretch=1)
        
        # Scale Slider
        slider_layout = QHBoxLayout()
        lbl_slider = QLabel("Kích thước Logo:" if lang == "vi" else "Logo Size:")
        slider_layout.addWidget(lbl_slider)
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(5, 60)  # 5% to 60%
        active_scale = logos[selected_index]["scale_pct"] if logos else 0.15
        self.slider.setValue(int(active_scale * 100))
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.slider)
        
        self.lbl_val = QLabel(f"{self.slider.value()}%")
        self.lbl_val.setFixedWidth(40)
        slider_layout.addWidget(self.lbl_val)
        layout.addLayout(slider_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("Lưu" if lang == "vi" else "Save")
        self.btn_save.setObjectName("SaveBtn")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        
        self.btn_cancel = QPushButton("Hủy" if lang == "vi" else "Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
    def _on_logo_selection_changed(self, index):
        if index < 0 or index >= len(self.preview_widget.logos):
            return
        self.preview_widget.selected_index = index
        scale_pct = self.preview_widget.logos[index]["scale_pct"]
        
        self.slider.blockSignals(True)
        self.slider.setValue(int(scale_pct * 100))
        self.lbl_val.setText(f"{self.slider.value()}%")
        self.slider.blockSignals(False)
        
        self.preview_widget.update()
        
    def select_logo(self, index):
        self.cmb_active.blockSignals(True)
        self.cmb_active.setCurrentIndex(index)
        self.cmb_active.blockSignals(False)
        
        scale_pct = self.preview_widget.logos[index]["scale_pct"]
        self.slider.blockSignals(True)
        self.slider.setValue(int(scale_pct * 100))
        self.lbl_val.setText(f"{self.slider.value()}%")
        self.slider.blockSignals(False)
        
    def _on_slider_changed(self, value):
        self.lbl_val.setText(f"{value}%")
        idx = self.preview_widget.selected_index
        if 0 <= idx < len(self.preview_widget.logos):
            self.preview_widget.logos[idx]["scale_pct"] = value / 100.0
            self.preview_widget.update()
            
    def get_values(self) -> list:
        return self.preview_widget.logos
