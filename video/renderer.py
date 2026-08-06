import cv2
import logging
from typing import Tuple
from utils.helpers import get_short_path_name

logger = logging.getLogger("AIDrawingVideo")

class VideoRenderer:
    def __init__(self, output_path: str, fps: int = 30, resolution: Tuple[int, int] = (1920, 1080)):
        self.output_path = output_path
        self.fps = fps
        self.width, self.height = resolution
        self.writer = None
        self._init_writer()

    def _init_writer(self) -> None:
        """Initializes the OpenCV VideoWriter object."""
        # 'mp4v' is highly compatible on Windows for direct rendering.
        # We will later re-encode the final video to clean H264 using FFmpeg.
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        
        logger.info(f"Initializing VideoWriter: {self.output_path} ({self.width}x{self.height} @ {self.fps}fps)")
        self.writer = cv2.VideoWriter(
            get_short_path_name(self.output_path),
            fourcc,
            self.fps,
            (self.width, self.height)
        )
        
        if not self.writer.isOpened():
            raise RuntimeError(f"Could not open VideoWriter for path: {self.output_path}")

    def write_frame(self, frame_bgr) -> None:
        """Writes a single BGR frame to the video stream."""
        if self.writer is None:
            raise RuntimeError("VideoWriter is not open or has been released.")
        self.writer.write(frame_bgr)

    def release(self) -> None:
        """Releases the VideoWriter resource."""
        if self.writer is not None:
            self.writer.release()
            self.writer = None
            logger.info("VideoWriter released.")
