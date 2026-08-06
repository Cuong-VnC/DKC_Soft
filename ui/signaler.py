from PySide6.QtCore import QObject, Signal

class PipelineSignaler(QObject):
    """
    QObject bridge defining Qt signals. Emitting these signals from the
    background thread allows the PySide6 main thread to safely update GUI widgets.
    """
    progress = Signal(float, str)  # Emits (fraction, status_text)
    preview = Signal(object)       # Emits (PIL.Image.Image)
    finished = Signal(bool, str)   # Emits (success, message)
