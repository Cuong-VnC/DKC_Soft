import os
import sys
import threading
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import QMainWindow, QTabWidget, QMessageBox, QApplication
from PySide6.QtCore import Slot, QObject, Signal
from PySide6.QtGui import QIcon

from ui.tab_multi import MultiVideoTab
from ui.config import QSS_STYLESHEET, LIGHT_QSS_STYLESHEET, TRANSLATIONS

from engine.pipeline import PipelineEngine
from tts.generator import EdgeTTSGenerator
from tts.capcut_generator import CapCutTTSGenerator
from utils.logger import register_log_callback, get_next_log
from utils.helpers import ensure_directories

class VoiceLoadSignaler(QObject):
    voices_loaded = Signal(list)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("DKC Drawing Video v26.7.30")
        self.resize(1200, 800)
        self.setMinimumSize(1100, 750)
        
        # Set Window Icon
        if getattr(sys, 'frozen', False):
            logo_path = os.path.join(os.path.dirname(sys.executable), "logo.ico")
            if not os.path.exists(logo_path) and hasattr(sys, '_MEIPASS'):
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
        else:
            logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logo.ico")
            
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        
        # Apply dark theme initially
        self.setStyleSheet(QSS_STYLESHEET)
        
        # Setup paths & engines
        self.dirs = ensure_directories()
        self.pipeline = PipelineEngine()
        self.tts = EdgeTTSGenerator()
        self.capcut_tts = CapCutTTSGenerator()
        self.voices_list: List[Dict[str, Any]] = []
        
        # Settings configuration
        self.current_lang = "vi"
        self.current_theme = "dark"
        
        # Signals (pipeline signaler is dynamically imported or handled)
        from ui.signaler import PipelineSignaler
        self.signaler = PipelineSignaler()
        self.voice_signaler = VoiceLoadSignaler()
        
        # Connect slots
        self.signaler.progress.connect(self._update_progress_gui)
        self.signaler.preview.connect(self._update_preview_canvas)
        self.signaler.finished.connect(self._on_render_finished)
        self.voice_signaler.voices_loaded.connect(self._on_voices_loaded)
        
        self.init_ui()
        
        # Load voices list asynchronously
        self._load_voices_async()
        
        # Log polling timer
        register_log_callback(self._on_log_received)
        self._start_log_timer()
        
    def init_ui(self) -> None:
        self.main_tabs = QTabWidget()
        self.main_tabs.setObjectName("MainTabs")
        self.main_tabs.tabBar().hide()
        self.setCentralWidget(self.main_tabs)
        
        # Tab 1: Multi video
        self.tab_multi = MultiVideoTab(
            self.dirs, self.current_lang, self.voices_list,
            self.start_render, self.pause_render, self.resume_render, self.cancel_render, self
        )
        self.main_tabs.addTab(self.tab_multi, "Video từng ảnh")
        
        self.update_ui_language(self.current_lang)

    def get_active_tab(self):
        return self.main_tabs.currentWidget()

    def get_current_settings(self) -> Dict[str, Any]:
        active_tab = self.get_active_tab()
        if hasattr(active_tab, "get_settings"):
            return active_tab.get_settings()
        return {}

    # --- SETTINGS / LANGUAGE / THEME CONFIGURATOR ---
    
    def apply_settings(self, lang: str, theme: str) -> None:
        self.current_lang = lang
        self.current_theme = theme
        
        # Apply theme stylesheet
        self.setStyleSheet(QSS_STYLESHEET if theme == "dark" else LIGHT_QSS_STYLESHEET)
        
        # Update tab languages and themes
        self.tab_multi.current_theme = theme
        self.tab_multi.update_language(lang)
        
        self.update_ui_language(lang)

    def update_ui_language(self, lang: str) -> None:
        t = TRANSLATIONS[lang]
        self.main_tabs.setTabText(0, t["tab_mode_multi"])

    # --- ASYNC VOICE LIST FETCHING ---

    def _load_voices_async(self) -> None:
        def run():
            edge_voices = self.tts.get_all_voices_sync()
            capcut_voices = self.capcut_tts.get_all_voices()
            self.voice_signaler.voices_loaded.emit([edge_voices, capcut_voices])
        threading.Thread(target=run, daemon=True).start()

    @Slot(list)
    def _on_voices_loaded(self, voice_lists: List[List[Dict[str, Any]]]) -> None:
        edge_voices, capcut_voices = voice_lists
        self.voices_list = edge_voices
        self.tab_multi.set_voices(edge_voices, capcut_voices)

    # --- LOG TIMER CONSOLE POLLING ---

    def _start_log_timer(self) -> None:
        self.log_timer = self.startTimer(100)

    def timerEvent(self, event) -> None:
        while True:
            log_line = get_next_log()
            if log_line is None:
                break
            self.tab_multi.append_log(log_line)
            
    def _on_log_received(self, log_line: str) -> None:
        pass

    # --- PIPELINE CONTROLLER DECK ---

    def start_render(self) -> None:
        active_tab = self.get_active_tab()
        settings = self.get_current_settings()
        
        if not settings or not settings.get("scenes"):
            QMessageBox.warning(self, "Cảnh báo" if self.current_lang == "vi" else "Warning", 
                                "Vui lòng thêm ít nhất một cảnh vẽ (Hình ảnh + Kịch bản)." if self.current_lang == "vi" else "Please add at least one scene (Image + Script).")
            return
            
        for sc in settings["scenes"]:
            if not sc["image_path"]:
                QMessageBox.warning(self, "Cảnh báo" if self.current_lang == "vi" else "Warning", 
                                    "Vui lòng chọn hình ảnh đầu vào đầy đủ." if self.current_lang == "vi" else "Please select a valid image.")
                return
                
        # Lock controls on active tab
        if hasattr(active_tab, "lock_controls"):
            active_tab.lock_controls()
            
        # Start pipeline worker thread
        self.pipeline.start_generation(
            settings,
            progress_cb=self.signaler.progress.emit,
            preview_cb=self.signaler.preview.emit,
            finished_cb=self.signaler.finished.emit
        )

    @Slot(float, str)
    def _update_progress_gui(self, fraction: float, status_text: str) -> None:
        active_tab = self.get_active_tab()
        if hasattr(active_tab, "update_progress"):
            active_tab.update_progress(fraction, status_text)

    @Slot(object)
    def _update_preview_canvas(self, img) -> None:
        active_tab = self.get_active_tab()
        if hasattr(active_tab, "update_preview"):
            active_tab.update_preview(img)

    @Slot(bool, str)
    def _on_render_finished(self, success: bool, msg: str) -> None:
        active_tab = self.get_active_tab()
        
        # Unlock controls on active tab
        if hasattr(active_tab, "unlock_controls"):
            active_tab.unlock_controls()
        
        if success:
            QMessageBox.information(self, "Thành công" if self.current_lang == "vi" else "Success", msg)
            if hasattr(active_tab, "update_progress"):
                active_tab.update_progress(1.0, "Hoàn thành." if self.current_lang == "vi" else "Finished.")
        else:
            QMessageBox.critical(self, "Thất bại" if self.current_lang == "vi" else "Failed", msg)
            if hasattr(active_tab, "update_progress"):
                active_tab.update_progress(0.0, "Thất bại." if self.current_lang == "vi" else "Failed.")

    def pause_render(self) -> None:
        self.pipeline.pause()
        active_tab = self.get_active_tab()
        if active_tab and hasattr(active_tab, "btn_pause"):
            active_tab.btn_pause.setEnabled(False)
            active_tab.btn_resume.setEnabled(True)
            active_tab.lbl_progress.setText("Tạm dừng tiến trình..." if self.current_lang == "vi" else "Pausing process...")

    def resume_render(self) -> None:
        self.pipeline.resume()
        active_tab = self.get_active_tab()
        if active_tab and hasattr(active_tab, "btn_pause"):
            active_tab.btn_pause.setEnabled(True)
            active_tab.btn_resume.setEnabled(False)
            active_tab.lbl_progress.setText("Đang tiếp tục..." if self.current_lang == "vi" else "Resuming...")

    def cancel_render(self) -> None:
        title = "Hủy Bỏ" if self.current_lang == "vi" else "Cancel"
        question = "Bạn có chắc chắn muốn hủy tiến trình render hiện tại không?" if self.current_lang == "vi" else "Are you sure you want to cancel the current render process?"
        if QMessageBox.question(self, title, question, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.pipeline.cancel()
