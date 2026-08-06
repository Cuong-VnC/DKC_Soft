import cv2
import numpy as np
from typing import List, Tuple

class ContourExtractor:
    def __init__(
        self,
        canny_low: int = 50,
        canny_high: int = 150,
        blur_kernel: int = 5,
        approx_epsilon: float = 0.002,
        min_length: int = 10
    ):
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.blur_kernel = blur_kernel
        self.approx_epsilon = approx_epsilon
        self.min_length = min_length

    def preprocess_image(self, img_path: str, target_res: Tuple[int, int], invert: bool = False) -> Tuple[np.ndarray, np.ndarray]:
        """
        Loads, resizes with aspect ratio preservation (padding with white),
        and returns the preprocessed grayscale and color images.
        """
        # Read image safely with Unicode path support
        try:
            with open(img_path, "rb") as f:
                file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            color_img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        except Exception:
            color_img = None
        if color_img is None:
            raise FileNotFoundError(f"Cannot read image at {img_path}")
            
        target_w, target_h = target_res
        
        # Calculate aspect ratio resize
        h, w = color_img.shape[:2]
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        resized = cv2.resize(color_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Create blank white padded canvas (or black canvas if inverted)
        pad_color = (0, 0, 0) if invert else (255, 255, 255)
        canvas_color = np.full((target_h, target_w, 3), pad_color, dtype=np.uint8)
        
        # Center the resized image
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2
        canvas_color[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        # Preprocessing for edges
        gray = cv2.cvtColor(canvas_color, cv2.COLOR_BGR2GRAY)
        
        # Bilateral filter to preserve edges while smoothing out noise
        blurred = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
        if self.blur_kernel > 0:
            # Ensure odd kernel size
            ksize = self.blur_kernel if self.blur_kernel % 2 == 1 else self.blur_kernel + 1
            blurred = cv2.GaussianBlur(blurred, (ksize, ksize), 0)
            
        return canvas_color, blurred

    def extract_contours(self, blurred_img: np.ndarray) -> List[np.ndarray]:
        """
        Runs Canny edge detection, extracts contours, simplifies them using approxPolyDP,
        and filters out noise.
        """
        edges = cv2.Canny(blurred_img, self.canny_low, self.canny_high)
        
        # Find all contours
        raw_contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        
        processed_contours = []
        for c in raw_contours:
            # Calculate length
            length = cv2.arcLength(c, False)
            if length < self.min_length:
                continue
                
            # Simplify contour
            epsilon = self.approx_epsilon * length
            approx = cv2.approxPolyDP(c, epsilon, closed=False)
            
            # Reshape approx to Nx2 array of coordinates
            pts = approx.reshape(-1, 2)
            if len(pts) >= 2:
                processed_contours.append(pts)
                
        return processed_contours

    @staticmethod
    def optimize_contour_order(contours: List[np.ndarray]) -> List[np.ndarray]:
        """
        Orders contours using a Nearest Neighbor (TSP) heuristic to minimize pen-up travel distance.
        Can reverse contours if drawing in reverse starting point is closer.
        """
        if not contours:
            return []
            
        unvisited = list(contours)
        ordered = []
        
        # Start with the contour closest to the top-left (0,0)
        current_idx = 0
        min_dist_to_origin = float('inf')
        for i, c in enumerate(unvisited):
            d = np.linalg.norm(c[0] - np.array([0, 0]))
            if d < min_dist_to_origin:
                min_dist_to_origin = d
                current_idx = i
                
        current = unvisited.pop(current_idx)
        ordered.append(current)
        
        while unvisited:
            last_pt = ordered[-1][-1]
            
            best_idx = 0
            best_dist = float('inf')
            reverse_needed = False
            
            # Find the closest contour (either start or end point)
            for i, c in enumerate(unvisited):
                # Distance to start point
                d_start = np.linalg.norm(c[0] - last_pt)
                # Distance to end point (can reverse)
                d_end = np.linalg.norm(c[-1] - last_pt)
                
                if d_start < best_dist:
                    best_dist = d_start
                    best_idx = i
                    reverse_needed = False
                if d_end < best_dist:
                    best_dist = d_end
                    best_idx = i
                    reverse_needed = True
            
            next_contour = unvisited.pop(best_idx)
            if reverse_needed:
                next_contour = next_contour[::-1]
            ordered.append(next_contour)
            
        return ordered

    def group_contours_spatially(self, contours: List[np.ndarray], grid_size: int = 4, draw_direction: str = "left_to_right") -> List[np.ndarray]:
        """
        Groups contours into a grid (e.g. 4x4) and draws them region-by-region (e.g., center-outwards or spiral)
        to make the animation feel natural. Within each region, contours are optimized via Nearest Neighbor.
        """
        if not contours:
            return []
            
        # Get bounding box of all contours to define grid coordinate limits
        all_pts = np.vstack(contours)
        min_x, min_y = np.min(all_pts, axis=0)
        max_x, max_y = np.max(all_pts, axis=0)
        
        w = max(max_x - min_x, 1)
        h = max(max_y - min_y, 1)
        
        # Assign each contour to a grid cell based on its centroid
        cells = { (r, c): [] for r in range(grid_size) for c in range(grid_size) }
        
        for c in contours:
            centroid = np.mean(c, axis=0)
            cx, cy = centroid
            
            # Normalize to 0..1
            nx = (cx - min_x) / w
            ny = (cy - min_y) / h
            
            # Determine cell row and column
            grid_col = min(int(nx * grid_size), grid_size - 1)
            grid_row = min(int(ny * grid_size), grid_size - 1)
            
            cells[(grid_row, grid_col)].append(c)
            
        # Define a drawing sequence for the grid cells based on draw_direction.
        if draw_direction == "left_to_right":
            sorted_cells = sorted(cells.keys(), key=lambda coord: (coord[1], coord[0]))
        elif draw_direction == "right_to_left":
            sorted_cells = sorted(cells.keys(), key=lambda coord: (-coord[1], coord[0]))
        elif draw_direction == "top_to_bottom":
            sorted_cells = sorted(cells.keys(), key=lambda coord: (coord[0], coord[1]))
        elif draw_direction == "bottom_to_top":
            sorted_cells = sorted(cells.keys(), key=lambda coord: (-coord[0], coord[1]))
        else:
            # Default center-outward order
            center_r = (grid_size - 1) / 2.0
            center_c = (grid_size - 1) / 2.0
            sorted_cells = sorted(cells.keys(), key=lambda coord: ((coord[0] - center_r) ** 2 + (coord[1] - center_c) ** 2, coord[0], coord[1]))
        
        final_ordered_contours = []
        for cell_coord in sorted_cells:
            cell_contours = cells[cell_coord]
            if not cell_contours:
                continue
            # Optimize the subset within this cell
            optimized_cell = self.optimize_contour_order(cell_contours)
            final_ordered_contours.extend(optimized_cell)
            
        return final_ordered_contours
        
    def get_drawing_strokes(self, img_path: str, target_res: Tuple[int, int], spatial_grouping: bool = True, invert: bool = False, draw_direction: str = "left_to_right") -> Tuple[np.ndarray, List[np.ndarray]]:
        """
        Convenience function that loads, extracts contours, and optimizes order.
        Returns the preprocessed color canvas and the list of ordered contours.
        """
        color_canvas, blurred = self.preprocess_image(img_path, target_res, invert)
        contours = self.extract_contours(blurred)
        
        if spatial_grouping:
            ordered = self.group_contours_spatially(contours, draw_direction=draw_direction)
        else:
            ordered = self.optimize_contour_order(contours)
            
        return color_canvas, ordered
