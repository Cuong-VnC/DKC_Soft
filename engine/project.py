import json
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger("AIDrawingVideo")

class ProjectManager:
    DEFAULT_SETTINGS = {
        "voice": "vi-VN-HoaiMyNeural",
        "rate": 0,
        "pitch": 0,
        "volume": 0,
        "fps": 30,
        "resolution": [1920, 1080],
        "pen_style": "Ink Pen",
        "pen_color": [0, 0, 0],
        "pen_width": 4.0,
        "pen_opacity": 1.0,
        "bg_style": "Whiteboard",
        "music_path": "",
        "voice_volume": 1.0,
        "music_volume": 0.15,
        "fade_in": 2.0,
        "fade_out": 3.0,
        "camera_enabled": True,
        "spatial_grouping": True,
        "color_option": "Outline then Color",
        "color_style": "gradual",
        "export_dir": "",
        "scenes": [],  # List of dicts: {"image_path": str, "script": str}
        "logos": []  # List of dicts: {"path": str, "cx_pct": float, "cy_pct": float, "scale_pct": float}
    }

    @staticmethod
    def save_project(filepath: str, data: Dict[str, Any]) -> bool:
        """Saves project configuration to a JSON file."""
        try:
            # Ensure folder exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Combine defaults with provided data
            project_data = {}
            for k, v in ProjectManager.DEFAULT_SETTINGS.items():
                project_data[k] = data.get(k, v)
                
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=4, ensure_ascii=False)
                
            logger.info(f"Project saved to: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            return False

    @staticmethod
    def load_project(filepath: str) -> Dict[str, Any]:
        """Loads project configuration from a JSON file."""
        if not os.path.exists(filepath):
            logger.warning(f"Project file not found: {filepath}")
            return dict(ProjectManager.DEFAULT_SETTINGS)
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                
            # Merge with defaults to ensure all keys exist
            project_data = dict(ProjectManager.DEFAULT_SETTINGS)
            project_data.update(loaded_data)
            
            logger.info(f"Project loaded from: {filepath}")
            return project_data
        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            return dict(ProjectManager.DEFAULT_SETTINGS)
