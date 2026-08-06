import sys
import os

# Add executable dir and its ffmpeg subdirectory to system PATH so that shutil.which and subprocess find them
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

ffmpeg_dir = os.path.join(app_dir, "ffmpeg")
paths_to_add = []
if os.path.exists(ffmpeg_dir):
    paths_to_add.append(ffmpeg_dir)
paths_to_add.append(app_dir)

for path in paths_to_add:
    if path not in os.environ["PATH"]:
        os.environ["PATH"] = path + os.pathsep + os.environ["PATH"]

import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow
from utils.logger import setup_logger
from auth import run_authentication

def check_ffmpeg_installed() -> bool:
    import shutil
    import subprocess
    import platform
    ffmpeg_exists = shutil.which("ffmpeg") is not None
    ffprobe_exists = shutil.which("ffprobe") is not None
    if not (ffmpeg_exists and ffprobe_exists):
        return False
    try:
        creation_flags = 0
        if platform.system() == "Windows":
            creation_flags = subprocess.CREATE_NO_WINDOW
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        return True
    except Exception:
        return False

def start_pyside_app():
    logger = logging.getLogger("AIDrawingVideo")
    try:
        # Create PySide6 Application
        qt_app = QApplication(sys.argv)
        
        # Check FFmpeg installation
        if not check_ffmpeg_installed():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                None,
                "Lỗi Hệ Thống",
                "Không tìm thấy FFmpeg hoặc ffprobe trên máy tính của bạn.\n\n"
                "Vui lòng cài đặt FFmpeg và thêm nó vào biến môi trường PATH để phần mềm hoạt động đúng cách.",
                QMessageBox.Ok
            )
            sys.exit(1)
        
        # Set Application Icon
        if getattr(sys, 'frozen', False):
            logo_path = os.path.join(os.path.dirname(sys.executable), "logo.ico")
            if not os.path.exists(logo_path) and hasattr(sys, '_MEIPASS'):
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
        else:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            
        if os.path.exists(logo_path):
            qt_app.setWindowIcon(QIcon(logo_path))
            
        # Create and show main window
        app = MainWindow()
        app.show()
        
        # Start Qt event loop
        sys.exit(qt_app.exec())
    except Exception as e:
        logger.critical(f"Unhandled exception in main application thread: {e}", exc_info=True)
        sys.exit(1)

def main():
    # Setup thread-safe logger
    setup_logger()
    
    # Run license key verification first, then start the main app on success
    run_authentication(start_pyside_app)

if __name__ == "__main__":
    main()
