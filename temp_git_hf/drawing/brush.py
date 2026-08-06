import random
from typing import Tuple
import numpy as np
from PIL import Image, ImageDraw

class Brush:
    _custom_brush_cache = {}

    @staticmethod
    def draw_segment(
        draw: ImageDraw.Draw,
        pt1: Tuple[float, float],
        pt2: Tuple[float, float],
        style: str,
        color: Tuple[int, int, int],
        base_width: float = 3.0,
        opacity: float = 1.0
    ) -> None:
        """
        Draws a stroke segment between pt1 and pt2 using the specified brush style,
        modulating thickness, opacity, and texture.
        """
        import os
        import math
        
        # Ensure coordinates are float tuples
        x1, y1 = pt1
        x2, y2 = pt2
        
        r, g, b = color
        alpha = int(255 * opacity)
        
        if os.path.exists(style):
            mask = Brush._custom_brush_cache.get(style)
            if mask is None:
                try:
                    img = Image.open(style)
                    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                        mask = img.convert("RGBA").split()[-1]
                    else:
                        mask = img.convert("L")
                    Brush._custom_brush_cache[style] = mask
                except Exception:
                    mask = None
                    
            if mask is not None:
                brush_size = max(4, int(base_width * 3.0))
                resized_mask = mask.resize((brush_size, brush_size), Image.Resampling.BILINEAR)
                
                dx = x2 - x1
                dy = y2 - y1
                dist = math.hypot(dx, dy)
                step = max(1.0, brush_size / 6.0)
                
                if dist > 0:
                    steps = max(1, int(dist / step))
                    for i in range(steps + 1):
                        t = i / steps
                        cx = x1 + t * dx
                        cy = y1 + t * dy
                        draw.bitmap((cx - brush_size/2, cy - brush_size/2), resized_mask, fill=(r, g, b, alpha))
                else:
                    draw.bitmap((x1 - brush_size/2, y1 - brush_size/2), resized_mask, fill=(r, g, b, alpha))
                return

        # Limit style to lower case
        style_lower = style.lower()
        
        if style_lower == "pencil":
            # Pencil: thin line, slight opacity, jitter and graphite texture
            pencil_width = max(1, int(base_width * 0.6))
            # Pencil color is usually graphite (dark gray/black) but we can blend with user color
            gray_level = int(0.299 * r + 0.587 * g + 0.114 * b)
            # Make it look like charcoal/graphite
            pc = (gray_level, gray_level, gray_level, int(alpha * 0.7))
            
            # Draw main line
            draw.line([(x1, y1), (x2, y2)], fill=pc, width=pencil_width)
            
            # Simulate graphite dust: draw occasional tiny random dots slightly offset
            length = np.linalg.norm(np.array(pt2) - np.array(pt1))
            if length > 2:
                num_dots = int(length / 2)
                for _ in range(num_dots):
                    t = random.random()
                    tx = x1 + t * (x2 - x1) + random.uniform(-1.0, 1.0)
                    ty = y1 + t * (y2 - y1) + random.uniform(-1.0, 1.0)
                    # Slightly lighter dust
                    dust_alpha = int(alpha * random.uniform(0.1, 0.4))
                    draw.point((tx, ty), fill=(gray_level, gray_level, gray_level, dust_alpha))
                    
        elif style_lower == "ink pen" or style_lower == "ink":
            # Ink Pen: clean, solid, high contrast, uniform thickness
            pen_width = max(1, int(base_width * 0.8))
            draw.line([(x1, y1), (x2, y2)], fill=(r, g, b, alpha), width=pen_width)
            
            # Tiny rounding at end points to make it super smooth
            draw.ellipse([x1 - pen_width/2, y1 - pen_width/2, x1 + pen_width/2, y1 + pen_width/2], fill=(r, g, b, alpha))
            draw.ellipse([x2 - pen_width/2, y2 - pen_width/2, x2 + pen_width/2, y2 + pen_width/2], fill=(r, g, b, alpha))

        elif style_lower == "marker":
            # Marker: thick, semi-transparent. Overlapping layers darken naturally.
            marker_width = int(base_width * 2.5)
            marker_alpha = int(alpha * 0.4)  # High transparency for marker build-up
            
            # Draw semi-transparent stroke
            draw.line([(x1, y1), (x2, y2)], fill=(r, g, b, marker_alpha), width=marker_width)
            # Rounded cap
            draw.ellipse([x1 - marker_width/2, y1 - marker_width/2, x1 + marker_width/2, y1 + marker_width/2], fill=(r, g, b, marker_alpha))
            draw.ellipse([x2 - marker_width/2, y2 - marker_width/2, x2 + marker_width/2, y2 + marker_width/2], fill=(r, g, b, marker_alpha))

        elif style_lower == "brush":
            # Brush: Soft, feathered edge simulation by drawing concentric strokes
            brush_width = int(base_width * 3.5)
            
            # Draw outer glow/feather: wide, very faint
            outer_w = brush_width
            outer_a = int(alpha * 0.15)
            draw.line([(x1, y1), (x2, y2)], fill=(r, g, b, outer_a), width=outer_w)
            draw.ellipse([x1 - outer_w/2, y1 - outer_w/2, x1 + outer_w/2, y1 + outer_w/2], fill=(r, g, b, outer_a))
            
            # Middle layer
            mid_w = int(brush_width * 0.6)
            mid_a = int(alpha * 0.35)
            draw.line([(x1, y1), (x2, y2)], fill=(r, g, b, mid_a), width=mid_w)
            draw.ellipse([x1 - mid_w/2, y1 - mid_w/2, x1 + mid_w/2, y1 + mid_w/2], fill=(r, g, b, mid_a))
            
            # Core stroke: thin, more solid
            core_w = int(brush_width * 0.25)
            core_w = max(1, core_w)
            core_a = int(alpha * 0.8)
            draw.line([(x1, y1), (x2, y2)], fill=(r, g, b, core_a), width=core_w)
            draw.ellipse([x1 - core_w/2, y1 - core_w/2, x1 + core_w/2, y1 + core_w/2], fill=(r, g, b, core_a))

        else:
            # Default fallback: solid line
            draw.line([(x1, y1), (x2, y2)], fill=(r, g, b, alpha), width=int(base_width))
