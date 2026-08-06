from typing import Optional
from PIL import Image
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QImage, QColor, QBrush
from PySide6.QtCore import Qt, QRect

class PreviewCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.qimage: Optional[QImage] = None
        self._img_data: Optional[bytes] = None  # Reference storage to prevent GC of raw buffer
        
        # Set dark theme background color
        self.bg_color = QColor(43, 43, 43)

    def set_image(self, pil_image: Image.Image) -> None:
        """Converts PIL image to QImage and triggers paint update."""
        if pil_image is None:
            self.clear()
            return
            
        # Convert PIL Image to RGBA format
        img_rgba = pil_image.convert("RGBA")
        width, height = img_rgba.size
        
        # Convert PIL image to raw bytes
        self._img_data = img_rgba.tobytes("raw", "RGBA")
        
        # Create QImage pointing to raw bytes
        # Pitch (bytes per line) is width * 4 (since it is RGBA)
        self.qimage = QImage(
            self._img_data,
            width,
            height,
            width * 4,
            QImage.Format_RGBA8888
        )
        
        # Request repaint
        self.update()

    def clear(self) -> None:
        """Clears the current image."""
        self.qimage = None
        self._img_data = None
        self.update()

    def paintEvent(self, event) -> None:
        """Draws the dark background and the QImage scaled to fit aspect ratio."""
        painter = QPainter(self)
        
        # Enable high-quality scaling (bilinear filtering)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Draw background
        painter.fillRect(self.rect(), self.bg_color)
        
        if self.qimage is None:
            painter.end()
            return
            
        # Get widget dimensions
        widget_w = self.width()
        widget_h = self.height()
        
        # Get image dimensions
        img_w = self.qimage.width()
        img_h = self.qimage.height()
        
        # Calculate aspect ratio scale factor
        scale = min(widget_w / img_w, widget_h / img_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))
        
        # Calculate centered offsets
        x_offset = (widget_w - new_w) // 2
        y_offset = (widget_h - new_h) // 2
        
        # Draw image
        target_rect = QRect(x_offset, y_offset, new_w, new_h)
        painter.drawImage(target_rect, self.qimage)
        
        painter.end()
