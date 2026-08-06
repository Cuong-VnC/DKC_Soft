import os
import random
import cv2
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from typing import Tuple, List, Optional
from drawing.brush import Brush

class DrawingRenderer:
    def __init__(
        self,
        resolution: Tuple[int, int] = (1920, 1080),
        bg_style: str = "whiteboard",
        pen_style: str = "ink pen",
        pen_color: Tuple[int, int, int] = (0, 0, 0),
        pen_width: float = 3.0,
        pen_opacity: float = 1.0,
        hand_img_path: Optional[str] = None,
        camera_enabled: bool = True
    ):
        self.width, self.height = resolution
        self.bg_style = bg_style
        self.pen_style = pen_style
        self.pen_color = pen_color
        self.pen_width = pen_width
        self.pen_opacity = pen_opacity
        self.camera_enabled = camera_enabled
        
        # Load hand image
        self.hand_img_path = hand_img_path
        self.hand_img = None
        if hand_img_path and os.path.exists(hand_img_path):
            try:
                self.hand_img = Image.open(hand_img_path).convert("RGBA")
            except Exception:
                pass
                
        # Camera states (center X, center Y, zoom)
        self.cam_x = self.width / 2.0
        self.cam_y = self.height / 2.0
        self.cam_zoom = 1.0
        
        # Hand rotation tilt state
        self.hand_tilt = 0.0
        
        # Initialize background image template
        self.bg_template = self._generate_background()

    def _generate_background(self) -> Image.Image:
        """Generates a premium background texture programmatically."""
        if os.path.exists(self.bg_style):
            try:
                img = Image.open(self.bg_style).convert("RGBA")
                return img.resize((self.width, self.height), Image.Resampling.LANCZOS)
            except Exception as e:
                import logging
                logger = logging.getLogger("AIDrawingVideo")
                logger.error(f"Failed to load custom background image '{self.bg_style}': {e}")
                
        bg_style_lower = self.bg_style.lower() if self.bg_style else ""
        if bg_style_lower == "blackboard":
            # Dark charcoal blackboard
            bg = Image.new("RGBA", (self.width, self.height), (25, 25, 25, 255))
            # Add very fine texture noise
            np_bg = np.array(bg)
            noise = np.random.normal(0, 3, np_bg[:, :, :3].shape)
            np_bg[:, :, :3] = np.clip(np_bg[:, :, :3] + noise, 0, 255).astype(np.uint8)
            return Image.fromarray(np_bg)
            
        elif bg_style_lower == "old paper":
            # Creamy vintage tan base
            bg = Image.new("RGBA", (self.width, self.height), (242, 230, 206, 255))
            np_bg = np.array(bg).astype(float)
            
            # 1. Add subtle paper grain noise
            noise = np.random.normal(0, 4, (self.height, self.width, 3))
            np_bg[:, :, :3] += noise
            
            # 2. Add vignette (darkening towards corners)
            x = np.linspace(-1, 1, self.width)
            y = np.linspace(-1, 1, self.height)
            xx, yy = np.meshgrid(x, y)
            d = np.sqrt(xx**2 + yy**2)
            # Vignette factor: darkens up to 15% at corners
            vignette = 1.0 - 0.15 * (d / np.sqrt(2))
            vignette = np.clip(vignette, 0.7, 1.0)[:, :, np.newaxis]
            
            np_bg[:, :, :3] *= vignette
            np_bg = np.clip(np_bg, 0, 255).astype(np.uint8)
            return Image.fromarray(np_bg)
            
        elif bg_style_lower == "canvas":
            # Linen texture
            bg = Image.new("RGBA", (self.width, self.height), (238, 235, 226, 255))
            np_bg = np.array(bg).astype(float)
            
            # Create horizontal and vertical linen thread lines
            h_lines = np.sin(np.arange(self.height) * (2 * np.pi / 4.0)) * 3.0
            v_lines = np.sin(np.arange(self.width) * (2 * np.pi / 4.0)) * 3.0
            
            # Add horizontal threads
            np_bg[:, :, :3] += h_lines[:, np.newaxis, np.newaxis]
            # Add vertical threads
            np_bg[:, :, :3] += v_lines[np.newaxis, :, np.newaxis]
            
            # Add a bit of fine noise
            noise = np.random.normal(0, 2, (self.height, self.width, 3))
            np_bg[:, :, :3] += noise
            
            np_bg = np.clip(np_bg, 0, 255).astype(np.uint8)
            return Image.fromarray(np_bg)
            
        elif bg_style_lower == "paper texture":
            # Fine drawing paper
            bg = Image.new("RGBA", (self.width, self.height), (250, 250, 247, 255))
            np_bg = np.array(bg).astype(float)
            noise = np.random.normal(0, 2, (self.height, self.width, 3))
            np_bg[:, :, :3] += noise
            np_bg = np.clip(np_bg, 0, 255).astype(np.uint8)
            return Image.fromarray(np_bg)
            
        else:
            # Whiteboard: clean off-white
            return Image.new("RGBA", (self.width, self.height), (255, 255, 255, 255))

    def update_camera(self, target_x: float, target_y: float, target_zoom: float, lerp: float = 0.08) -> None:
        """Interpolates camera coordinates and zoom factors for smooth movement."""
        if not self.camera_enabled:
            self.cam_x = self.width / 2.0
            self.cam_y = self.height / 2.0
            self.cam_zoom = 1.0
            return
            
        self.cam_x += lerp * (target_x - self.cam_x)
        self.cam_y += lerp * (target_y - self.cam_y)
        self.cam_zoom += lerp * (target_zoom - self.cam_zoom)
        
        # Clamp zoom to reasonable values
        self.cam_zoom = max(1.0, min(self.cam_zoom, 2.0))

    def apply_camera(self, img: Image.Image) -> Image.Image:
        """Crops and resizes the image based on current camera parameters."""
        if not self.camera_enabled or self.cam_zoom <= 1.01:
            return img
            
        cam_w = self.width / self.cam_zoom
        cam_h = self.height / self.cam_zoom
        
        left = self.cam_x - cam_w / 2.0
        top = self.cam_y - cam_h / 2.0
        right = self.cam_x + cam_w / 2.0
        bottom = self.cam_y + cam_h / 2.0
        
        # Clamp camera to image boundaries
        if left < 0:
            right -= left
            left = 0
        if right > self.width:
            left -= (right - self.width)
            right = self.width
        if top < 0:
            bottom -= top
            top = 0
        if bottom > self.height:
            top -= (bottom - self.height)
            bottom = self.height
            
        left, top, right, bottom = max(0, int(left)), max(0, int(top)), min(self.width, int(right)), min(self.height, int(bottom))
        
        # Crop and resize
        cropped = img.crop((left, top, right, bottom))
        return cropped.resize((self.width, self.height), Image.Resampling.LANCZOS)

    def draw_hand(self, img: Image.Image, x: float, y: float, angle_rad: float = 0.0) -> Image.Image:
        """Overlays the hand PNG rotated according to the drawing angle, aligning tip to (x, y)."""
        if self.hand_img is None:
            return img
            
        # Create a copy to overlay the hand
        frame = img.copy()
        hand_w, hand_h = self.hand_img.size
        
        # Identify brush name and set pen tip coordinate and arm direction
        filename = os.path.basename(self.hand_img_path).lower() if hasattr(self, "hand_img_path") and self.hand_img_path else ""
        
        if "hand-1" in filename:
            tip_x, tip_y = 7.0, 0.0
            arm_dir = "down"
        elif "hand-2" in filename or "hand-3" in filename:
            tip_x, tip_y = 509.0, 12.0
            arm_dir = "down"
        else:
            # Default hand
            tip_x, tip_y = 0.0, float(hand_h)
            arm_dir = "up"
            
        # Dynamically calculate the required scale so the wrist always goes off-screen
        padding = 150.0
        if arm_dir == "down":
            required_len = self.height - y + padding
            # tip is at top, wrist is at bottom
            dist_to_wrist = hand_h - tip_y
            scale = required_len / dist_to_wrist
            scale = max(0.4, min(scale, 1.2))
        else:
            required_len = y + padding
            # tip is at bottom, wrist is at top
            dist_to_wrist = tip_y if tip_y > 0 else hand_h
            scale = required_len / dist_to_wrist
            scale = max(0.5, min(scale, 1.5))
            
        # Resize the hand image and scale tip coordinates
        resized_w = max(1, int(hand_w * scale))
        resized_h = max(1, int(hand_h * scale))
        scaled_hand = self.hand_img.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
        scaled_tip_x = tip_x * scale
        scaled_tip_y = tip_y * scale
        
        # Calculate target tilt based on draw direction:
        # Cosine represents left/right movement, Sine represents up/down movement.
        target_tilt = 12.0 * math.cos(angle_rad) + 5.0 * math.sin(angle_rad)
        target_tilt = max(-15.0, min(target_tilt, 15.0))
        
        # Smoothly interpolate tilt to prevent snapping
        self.hand_tilt += 0.15 * (target_tilt - self.hand_tilt)
        
        # Rotate hand image about the scaled pen tip
        # Note: rotation is counter-clockwise in PIL, so negative tilt rotates clockwise (natural).
        rotated_hand = scaled_hand.rotate(
            -self.hand_tilt,
            resample=Image.Resampling.BICUBIC,
            center=(scaled_tip_x, scaled_tip_y)
        )
        
        # Calculate paste position to align pen tip to (x, y)
        paste_x = int(x - scaled_tip_x)
        paste_y = int(y - scaled_tip_y)
        
        # Paste with alpha transparency
        frame.paste(rotated_hand, (paste_x, paste_y), rotated_hand)
        return frame

    def render_frame(
        self,
        outline_canvas: Image.Image,
        color_canvas_pil: Image.Image,
        reveal_mask: Image.Image,
        current_pt: Optional[Tuple[float, float]],
        color_option: str,
        target_zoom: float = 1.0,
        drawing_angle: float = 0.0,
        outline_opacity: float = 1.0
    ) -> np.ndarray:
        """
        Renders a single frame.
        - Blends outline and color image based on color option and reveal_mask.
        - Applies camera zoom and pan.
        - Overlays the drawing hand.
        - Returns a BGR numpy array ready for OpenCV VideoWriter.
        """
        # 1. Start with background template
        frame_img = self.bg_template.copy()
        
        # 2. Draw outlines
        # If blackboard is selected, we invert the outline canvas (so black lines draw white)
        outlines = outline_canvas
        if self.bg_style and self.bg_style.lower() == "blackboard":
            # If pen is black, invert to white; otherwise keep colored outline
            if self.pen_color == (0, 0, 0):
                r, g, b, a = outline_canvas.split()
                # Invert colors for RGB
                inv_rgb = ImageOps.invert(Image.merge("RGB", (r, g, b)))
                outlines = Image.merge("RGBA", (inv_rgb.split()[0], inv_rgb.split()[1], inv_rgb.split()[2], a))
                
        if outline_opacity <= 0.0:
            outlines = None
        elif outline_opacity < 1.0:
            outlines = outlines.copy()
            alpha = outlines.getchannel('A').point(lambda p: int(p * outline_opacity))
            outlines.putalpha(alpha)
            
        if outlines is not None:
            frame_img.alpha_composite(outlines)
        
        # 3. Blend in the colored image if coloring is enabled
        color_option = color_option.lower()
        if "color" in color_option:
            # Apply reveal mask to the color image
            masked_color = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            masked_color.paste(color_canvas_pil, (0, 0), reveal_mask)
            
            # Compound onto background + outline
            # We composite color under or over outline
            bg_and_color = self.bg_template.copy()
            bg_and_color.alpha_composite(masked_color)
            if color_option != "only color" and outlines is not None:
                bg_and_color.alpha_composite(outlines)
            frame_img = bg_and_color
            
        # 4. Handle camera zoom & pan tracking
        if self.camera_enabled and current_pt is not None:
            self.update_camera(current_pt[0], current_pt[1], target_zoom)
            frame_img = self.apply_camera(frame_img)
            
            # If camera is zoomed, the hand coordinates must also be transformed to the zoomed screen coordinate!
            # Transform (x,y) point to screen space
            cam_w = self.width / self.cam_zoom
            cam_h = self.height / self.cam_zoom
            left = self.cam_x - cam_w / 2.0
            top = self.cam_y - cam_h / 2.0
            
            # Ensure boundaries clamp identical to apply_camera
            if left < 0: left = 0
            if left + cam_w > self.width: left = self.width - cam_w
            if top < 0: top = 0
            if top + cam_h > self.height: top = self.height - cam_h
            
            screen_x = (current_pt[0] - left) * self.cam_zoom
            screen_y = (current_pt[1] - top) * self.cam_zoom
        else:
            screen_x, screen_y = current_pt[0] if current_pt else 0, current_pt[1] if current_pt else 0
            
        # 5. Overlay the drawing hand (if drawing is active)
        if current_pt is not None:
            frame_img = self.draw_hand(frame_img, screen_x, screen_y, drawing_angle)
            
        # 6. Convert RGBA to BGR numpy array for OpenCV VideoWriter
        np_frame = np.array(frame_img)
        bgr_frame = cv2.cvtColor(np_frame, cv2.COLOR_RGBA2BGR)
        return bgr_frame

    def render_slide_transition(
        self,
        img_prev: np.ndarray,
        img_next: np.ndarray,
        frame_idx: int,
        total_frames: int
    ) -> np.ndarray:
        """
        Renders a single frame of a slide transition from img_prev to img_next.
        The old frame slides off to the left, and the new frame slides in from the right.
        Uses ease-in-out interpolation for smooth movement.
        """
        # Calculate eased fraction
        t = frame_idx / float(total_frames)
        t_eased = t * t * (3.0 - 2.0 * t)  # Cubic ease-in-out
        
        offset_x = int(self.width * t_eased)
        
        # Create output frame
        out_frame = np.zeros_like(img_next)
        
        # Copy previous frame shifted left
        if offset_x < self.width:
            out_frame[:, 0 : self.width - offset_x] = img_prev[:, offset_x : self.width]
            
        # Copy next frame sliding in from the right
        if offset_x > 0:
            out_frame[:, self.width - offset_x : self.width] = img_next[:, 0 : offset_x]
            
        return out_frame

    @staticmethod
    def generate_coloring_paths(contours: List[np.ndarray], target_res: Tuple[int, int]) -> List[Tuple[float, float]]:
        """
        Generates a sequence of points to simulate hand movements during the coloring phase.
        It samples centroids of contours, plus grid-sampled internal points.
        """
        w, h = target_res
        points = []
        
        # Add centroids of closed-ish contours
        for c in contours:
            if len(c) > 5:
                # Centroid
                centroid = np.mean(c, axis=0)
                points.append((float(centroid[0]), float(centroid[1])))
                
        # If too few points, sample in a grid
        if len(points) < 10:
            for y in range(int(h*0.1), int(h*0.9), 100):
                for x in range(int(w*0.1), int(w*0.9), 100):
                    points.append((float(x), float(y)))
                    
        # Filter points to make sure they are within canvas
        valid_points = []
        for x, y in points:
            if 0 <= x < w and 0 <= y < h:
                valid_points.append((x, y))
                
        # Sort points in simple reading order or spatial nearest neighbor
        if not valid_points:
            return []
            
        ordered_points = [valid_points[0]]
        unvisited = valid_points[1:]
        
        while unvisited:
            last = ordered_points[-1]
            best_idx = 0
            best_dist = float('inf')
            for i, p in enumerate(unvisited):
                d = (p[0] - last[0])**2 + (p[1] - last[1])**2
                if d < best_dist:
                    best_dist = d
                    best_idx = i
            ordered_points.append(unvisited.pop(best_idx))
            
        return ordered_points
