from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QGridLayout, QComboBox
from ui.config import TRANSLATIONS

class SettingsTab(QWidget):
    def __init__(self, current_lang: str, current_theme: str, on_changed_cb, parent=None):
        super().__init__(parent)
        self.current_lang = current_lang
        self.current_theme = current_theme
        self.on_changed_cb = on_changed_cb
        self.init_ui()
        
    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        self.lbl_settings_title = QLabel()
        self.lbl_settings_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #ffffff; margin-bottom: 10px;")
        layout.addWidget(self.lbl_settings_title)
        
        form_frame = QFrame()
        form_frame.setObjectName("SceneRowFrame")
        form_layout = QGridLayout(form_frame)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(15)
        
        self.lbl_settings_lang = QLabel()
        self.lbl_settings_lang.setStyleSheet("font-weight: bold; font-size: 12px;")
        form_layout.addWidget(self.lbl_settings_lang, 0, 0)
        
        self.cmb_settings_lang = QComboBox()
        self.cmb_settings_lang.addItem("Tiếng Việt", "vi")
        self.cmb_settings_lang.addItem("English", "en")
        idx_lang = self.cmb_settings_lang.findData(self.current_lang)
        if idx_lang >= 0:
            self.cmb_settings_lang.setCurrentIndex(idx_lang)
        self.cmb_settings_lang.currentIndexChanged.connect(self._on_changed)
        form_layout.addWidget(self.cmb_settings_lang, 0, 1)
        
        self.lbl_settings_theme = QLabel()
        self.lbl_settings_theme.setStyleSheet("font-weight: bold; font-size: 12px;")
        form_layout.addWidget(self.lbl_settings_theme, 1, 0)
        
        self.cmb_settings_theme = QComboBox()
        self.cmb_settings_theme.addItem("Tối / Dark", "dark")
        self.cmb_settings_theme.addItem("Sáng / Light", "light")
        idx_theme = self.cmb_settings_theme.findData(self.current_theme)
        if idx_theme >= 0:
            self.cmb_settings_theme.setCurrentIndex(idx_theme)
        self.cmb_settings_theme.currentIndexChanged.connect(self._on_changed)
        form_layout.addWidget(self.cmb_settings_theme, 1, 1)
        
        layout.addWidget(form_frame)
        layout.addStretch()
        
        self.update_language(self.current_lang)
        
    def _on_changed(self) -> None:
        lang = self.cmb_settings_lang.currentData()
        theme = self.cmb_settings_theme.currentData()
        self.current_lang = lang
        self.current_theme = theme
        self.on_changed_cb(lang, theme)
        
    def update_language(self, lang: str) -> None:
        t = TRANSLATIONS[lang]
        self.lbl_settings_title.setText(t["settings_title"])
        self.lbl_settings_lang.setText(t["settings_lang"])
        self.lbl_settings_theme.setText(t["settings_theme"])
