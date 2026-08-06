import logging
import queue
from typing import Callable, List, Optional

# Thread-safe log queue for UI polling
log_queue: queue.Queue = queue.Queue()
_callbacks: List[Callable[[str], None]] = []

class QueueHandler(logging.Handler):
    """
    Custom logging handler that pushes log records into a queue
    and triggers registered UI callbacks.
    """
    def emit(self, record: logging.LogRecord) -> None:
        log_entry = self.format(record)
        log_queue.put(log_entry)
        for callback in _callbacks:
            try:
                callback(log_entry)
            except Exception:
                pass  # UI callback might fail if UI is updating

def setup_logger() -> logging.Logger:
    """Configures the root logger and adds custom QueueHandler."""
    logger = logging.getLogger("AIDrawingVideo")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if setup is called multiple times
    if not logger.handlers:
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
        
        # Console handler
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
        
        # Queue handler for UI
        q_handler = QueueHandler()
        q_handler.setFormatter(formatter)
        logger.addHandler(q_handler)
        
    return logger

logger = setup_logger()

def register_log_callback(callback: Callable[[str], None]) -> None:
    """Registers a callback to receive logs in real-time."""
    if callback not in _callbacks:
        _callbacks.append(callback)

def unregister_log_callback(callback: Callable[[str], None]) -> None:
    """Unregisters a callback."""
    if callback in _callbacks:
        _callbacks.remove(callback)

def get_next_log() -> Optional[str]:
    """Retrieves the oldest log from the queue (non-blocking)."""
    try:
        return log_queue.get_nowait()
    except queue.Empty:
        return None
