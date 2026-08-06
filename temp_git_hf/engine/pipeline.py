import os
import time
import math
import asyncio
import threading
import logging
import subprocess
from typing import List, Dict, Any, Callable, Optional, Tuple
from PIL import Image, ImageDraw
import cv2
import numpy as np
import platform

creation_flags = 0
if platform.system() == "Windows":
    creation_flags = subprocess.CREATE_NO_WINDOW

from drawing.extractor import ContourExtractor
from drawing.renderer import DrawingRenderer
from drawing.brush import Brush
from tts.generator import EdgeTTSGenerator
from tts.capcut_generator import CapCutTTSGenerator
from video.renderer import VideoRenderer
from video.audio import AudioMerger
from utils.helpers import ensure_directories, get_hand_image_path, clean_temp_dir, get_short_path_name

logger = logging.getLogger("AIDrawingVideo")

def parse_timestamp_to_seconds(ts_str: str) -> float:
    try:
        parts = ts_str.split("-->")
        if len(parts) == 2:
            start_str = parts[0].strip().replace(",", ".")
            end_str = parts[1].strip().replace(",", ".")
            def to_sec(time_str):
                h, m, s = time_str.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
            return to_sec(end_str) - to_sec(start_str)
    except Exception:
        pass
    return 8.0


def overlay_logos(frame_bgr: np.ndarray, logos: List[Dict[str, Any]]) -> np.ndarray:
    if not logos:
        return frame_bgr
        
    out = frame_bgr.copy()
    fh, fw = out.shape[:2]
    
    for logo in logos:
        path = logo.get("path", "")
        if not path or not os.path.exists(path):
            continue
            
        cx_pct = logo.get("cx_pct", 0.5)
        cy_pct = logo.get("cy_pct", 0.5)
        scale_pct = logo.get("scale_pct", 0.15)
        
        logo_img = cv2.imread(get_short_path_name(path), cv2.IMREAD_UNCHANGED)
        if logo_img is None:
            continue
            
        lw = int(fw * scale_pct)
        if lw <= 0:
            continue
            
        lh_orig, lw_orig = logo_img.shape[:2]
        if lw_orig <= 0:
            continue
        lh = int(lw * lh_orig / lw_orig)
        if lh <= 0:
            continue
            
        logo_resized = cv2.resize(logo_img, (lw, lh), interpolation=cv2.INTER_AREA)
        
        lx = int(fw * cx_pct - lw / 2)
        ly = int(fh * cy_pct - lh / 2)
        
        x1 = max(0, lx)
        y1 = max(0, ly)
        x2 = min(fw, lx + lw)
        y2 = min(fh, ly + lh)
        
        lx1 = x1 - lx
        ly1 = y1 - ly
        lx2 = lx1 + (x2 - x1)
        ly2 = ly1 + (y2 - y1)
        
        if (x2 - x1) <= 0 or (y2 - y1) <= 0:
            continue
            
        logo_crop = logo_resized[ly1:ly2, lx1:lx2]
        if logo_crop.shape[2] == 4:
            alpha = logo_crop[:, :, 3:4] / 255.0
            logo_rgb = logo_crop[:, :, :3]
            out[y1:y2, x1:x2] = (1.0 - alpha) * out[y1:y2, x1:x2] + alpha * logo_rgb
        else:
            out[y1:y2, x1:x2] = logo_crop
            
    return out

class PipelineEngine:
    def __init__(self):
        self._is_paused = False
        self._is_cancelled = False
        self._pause_cond = threading.Condition()
        self._thread: Optional[threading.Thread] = None

    def start_generation(
        self,
        project_data: Dict[str, Any],
        progress_cb: Callable[[float, str], None],
        preview_cb: Callable[[Image.Image], None],
        finished_cb: Callable[[bool, str], None]
    ) -> None:
        """Starts the video generation process in a background thread."""
        self._is_paused = False
        self._is_cancelled = False
        
        self._thread = threading.Thread(
            target=self._run_pipeline,
            args=(project_data, progress_cb, preview_cb, finished_cb),
            daemon=True
        )
        self._thread.start()

    def pause(self) -> None:
        """Pauses the current rendering task."""
        with self._pause_cond:
            self._is_paused = True
            logger.info("Pipeline paused.")

    def resume(self) -> None:
        """Resumes the paused rendering task."""
        with self._pause_cond:
            self._is_paused = False
            self._pause_cond.notify_all()
            logger.info("Pipeline resumed.")

    def cancel(self) -> None:
        """Cancels the current rendering task."""
        self._is_cancelled = True
        # Wake up thread if it was paused so it can exit
        with self._pause_cond:
            self._is_paused = False
            self._pause_cond.notify_all()
        logger.info("Pipeline cancellation requested.")

    def _check_pause_and_cancel(self) -> bool:
        """Helper to block if paused and return True if cancelled."""
        if self._is_cancelled:
            return True
            
        with self._pause_cond:
            while self._is_paused:
                if self._is_cancelled:
                    return True
                self._pause_cond.wait(timeout=0.1)
                
        return self._is_cancelled

    def _run_pipeline(
        self,
        data: Dict[str, Any],
        progress_cb: Callable[[float, str], None],
        preview_cb: Callable[[Image.Image], None],
        finished_cb: Callable[[bool, str], None]
    ) -> None:
        """Executes the pipeline steps."""
        clean_temp_dir()
        dirs = ensure_directories()
        
        # Read configurations
        scenes = data.get("scenes", [])
        mode = data.get("mode", "video_voice")
        if not scenes:
            finished_cb(False, "Không có kịch bản hoặc hình ảnh nào để xử lý.")
            return
            
        voice = data.get("voice", "vi-VN-HoaiMyNeural")
        rate = data.get("rate", 0)
        pitch = data.get("pitch", 0)
        volume = data.get("volume", 0)
        fps = data.get("fps", 30)
        resolution = tuple(data.get("resolution", [1920, 1080]))
        
        pen_style = data.get("pen_style", "Ink Pen")
        pen_color = tuple(data.get("pen_color", [0, 0, 0]))
        pen_width = data.get("pen_width", 4.0)
        pen_opacity = data.get("pen_opacity", 1.0)
        draw_direction = data.get("draw_direction", "left_to_right")
        
        # Determine hand image path and actual pen style based on selected brush style
        hand_img_path = get_hand_image_path()
        actual_pen_style = pen_style
        if os.path.exists(pen_style):
            filename = os.path.basename(pen_style).lower()
            if "hand-" in filename or filename.startswith("hand"):
                hand_img_path = pen_style
                actual_pen_style = "Ink Pen"
            else:
                actual_pen_style = pen_style
        bg_style = data.get("bg_style", "Whiteboard")
        
        music_path = data.get("music_path", "")
        voice_volume = data.get("voice_volume", 1.0)
        music_volume = data.get("music_volume", 0.15)
        fade_in = data.get("fade_in", 2.0)
        fade_out = data.get("fade_out", 3.0)
        
        camera_enabled = data.get("camera_enabled", True)
        spatial_grouping = data.get("spatial_grouping", True)
        color_option = data.get("color_option", "Outline then Color")
        color_style = data.get("color_style", "gradual")
        slide_transition = data.get("slide_transition", True)
        export_dir = data.get("export_dir", dirs["output"])
        export_mode = data.get("export_mode", "merged")
        logos = data.get("logos", [])
        
        # Temp scene files lists
        scene_videos: List[str] = []
        scene_audios: List[str] = []
        video_durations: List[float] = []
        scene_numbers: List[int] = []
        
        tts_model = data.get("tts_model", "Edge-TTS")
        if tts_model == "CapCut TTS":
            tts_generator = CapCutTTSGenerator()
        else:
            tts_generator = EdgeTTSGenerator()
        extractor = ContourExtractor(
            canny_low=50,
            canny_high=150,
            blur_kernel=5,
            approx_epsilon=0.002,
            min_length=8
        )
        
        total_scenes = len(scenes)
        start_time = time.time()
        
        try:
            for idx, scene in enumerate(scenes):
                if self._check_pause_and_cancel():
                    finished_cb(False, "Đã hủy bỏ tiến trình.")
                    return
                    
                scene_num = idx + 1
                
                # Calculate transition padding for this scene
                t_next = 0.0
                if idx < total_scenes - 1:
                    next_trans = scenes[idx+1].get("transition", "none")
                    if next_trans != "none":
                        t_next = 0.5
                
                scene_color_style = color_style
                if scene_color_style == "random":
                    import random
                    scene_color_style = random.choice([
                        "diagonal_l2r",
                        "diagonal_r2l",
                        "straight_l2r",
                        "straight_r2l",
                        "immediate",
                        "gradual"
                    ])
                
                # Override coloring style to match drawing direction for unified animation
                if draw_direction == "left_to_right":
                    scene_color_style = "straight_l2r"
                elif draw_direction == "right_to_left":
                    scene_color_style = "straight_r2l"
                elif draw_direction == "top_to_bottom":
                    scene_color_style = "straight_t2b"
                elif draw_direction == "bottom_to_top":
                    scene_color_style = "straight_b2t"
                logger.info(f"Scene {scene_num} using coloring style: {scene_color_style}")
                
                img_path = scene.get("image_path", "")
                script = scene.get("script", "")
                
                if not img_path or not os.path.exists(img_path):
                    logger.warning(f"Scene {scene_num}: Image path invalid or missing. Skipping.")
                    continue
                    
                duration = 5.0
                ts = scene.get("timestamp", "")
                T_total = parse_timestamp_to_seconds(ts) if ts else 0.0

                if mode == "video_voice":
                    progress_cb((idx / total_scenes) * 0.9, f"Cảnh {scene_num}/{total_scenes}: Đang tạo TTS voice...")
                    
                    # Step 1: Generate Voice
                    voice_temp_path = os.path.join(dirs["temp"], f"scene_{scene_num}_raw.mp3")
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        voice_dur = loop.run_until_complete(
                            tts_generator.generate_voice(
                                text=script,
                                voice=voice,
                                output_path=voice_temp_path,
                                rate=rate,
                                pitch=pitch,
                                volume=volume
                            )
                        )
                    except Exception as e:
                        logger.error(f"TTS generation error for Scene {scene_num}: {e}")
                        voice_dur = 8.0
                        dummy_cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-c:a", "libmp3lame", "-t", str(voice_dur), voice_temp_path]
                        subprocess.run(dummy_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
                    finally:
                        loop.close()
                    
                    if ts:
                        hold_time = 0.5
                        duration = max(0.1, T_total - hold_time)
                    else:
                        duration = voice_dur
                    
                    # Pad audio with silence at the end if t_next > 0 or ts is present
                    final_voice_temp_path = os.path.join(dirs["temp"], f"scene_{scene_num}.mp3")
                    target_voice_len = T_total + t_next if ts else duration + t_next
                    
                    if t_next > 0 or ts:
                        pad_cmd = [
                            "ffmpeg", "-y",
                            "-i", voice_temp_path,
                            "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1",
                            "-t", f"{target_voice_len:.3f}",
                            final_voice_temp_path
                        ]
                        logger.info(f"Padding scene {scene_num} voice by {t_next}s: {' '.join(pad_cmd)}")
                        subprocess.run(pad_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, creationflags=creation_flags)
                    else:
                        import shutil
                        shutil.copy(voice_temp_path, final_voice_temp_path)
                        
                    scene_audios.append(final_voice_temp_path)
                else:
                    # Video-only mode
                    if ts:
                        hold_time = float(scene.get("hold_time", 0.0))
                        duration = max(0.1, T_total - hold_time)
                    else:
                        draw_time = float(scene.get("draw_time", 5.0))
                        duration = draw_time
                
                if self._check_pause_and_cancel():
                    finished_cb(False, "Đã hủy bỏ tiến trình.")
                    return
                    
                # Step 2: Extract & Optimize Contours
                progress_cb((idx / total_scenes) * 0.9 + (0.05 / total_scenes), f"Cảnh {scene_num}/{total_scenes}: Đang tối ưu nét vẽ...")
                
                invert_bg = (bg_style.lower() == "blackboard")
                color_canvas_np, contours = extractor.get_drawing_strokes(
                    img_path,
                    resolution,
                    spatial_grouping=spatial_grouping,
                    invert=invert_bg,
                    draw_direction=draw_direction
                )
                color_canvas_pil = Image.fromarray(cv2.cvtColor(color_canvas_np, cv2.COLOR_BGR2RGBA))
                
                if self._check_pause_and_cancel():
                    finished_cb(False, "Đã hủy bỏ tiến trình.")
                    return
                    
                # Step 3: Parse timing details
                phrases = EdgeTTSGenerator.analyze_punctuation_timing(script, duration)
                
                if mode == "video_voice":
                    if ts:
                        hold_time = 0.5
                        total_frames = int((duration + hold_time + t_next) * fps)
                    else:
                        total_frames = int((duration + t_next) * fps)
                else:
                    hold_time = float(scene.get("hold_time", 3.0))
                    total_frames = int((duration + hold_time + t_next) * fps)
                if total_frames <= 0:
                    total_frames = 1
                    
                t_frames = 0
                final_frames = 1
                
                drawing_budget_frames = int(duration * fps) - t_frames - final_frames
                if drawing_budget_frames < 1:
                    drawing_budget_frames = 1
                    
                segment_to_contour_idx: List[int] = []
                all_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
                for c_idx, c in enumerate(contours):
                    for i in range(len(c) - 1):
                        all_segments.append((tuple(c[i]), tuple(c[i+1])))
                        segment_to_contour_idx.append(c_idx)
                        
                total_segments = len(all_segments)
                
                total_jumps = 0
                if total_segments > 0:
                    current_pos = (resolution[0] / 2, resolution[1] / 2)
                    for seg_idx, (pt1, pt2) in enumerate(all_segments):
                        dist = math.hypot(pt1[0] - current_pos[0], pt1[1] - current_pos[1])
                        if dist > 20.0 and seg_idx > 0:
                            total_jumps += 1
                        current_pos = pt2
                        
                color_active = "color" in color_option.lower()
                outline_then_color = color_option.lower() == "outline then color"
                only_color = color_option.lower() == "only color"
                
                if only_color:
                    outline_frames = 0
                    color_frames = drawing_budget_frames
                elif color_active and outline_then_color:
                    outline_frames = int(drawing_budget_frames * 0.75)
                    if outline_frames < 1:
                        outline_frames = 1
                    color_frames = drawing_budget_frames - outline_frames
                else:
                    outline_frames = drawing_budget_frames
                    color_frames = 0
                    
                max_jump_frames = int(outline_frames * 0.3)
                if total_jumps > 0:
                    steps_per_jump = max_jump_frames // total_jumps
                    if steps_per_jump >= 1:
                        steps_per_jump = min(5, steps_per_jump)
                        actual_jump_frames = total_jumps * steps_per_jump
                    else:
                        steps_per_jump = 0
                        actual_jump_frames = 0
                    drawing_outline_frames = outline_frames - actual_jump_frames
                else:
                    steps_per_jump = 5
                    drawing_outline_frames = outline_frames
                    
                total_speak_duration = sum(p["speak_duration"] for p in phrases)
                if total_speak_duration == 0:
                    total_speak_duration = 1
                    
                segments_allocated = 0
                for i, p in enumerate(phrases):
                    ratio = p["speak_duration"] / total_speak_duration
                    p_segs = int(ratio * total_segments)
                    if i == len(phrases) - 1:
                        p_segs = total_segments - segments_allocated
                    p["segments_count"] = p_segs
                    segments_allocated += p_segs
                    
                phrase_timeline = []
                for p in phrases:
                    p_speak_frames = int((p["speak_duration"] / duration) * drawing_outline_frames)
                    p_pause_frames = int((p["pause"] / duration) * drawing_outline_frames)
                    phrase_timeline.append({
                        "speak_frames": p_speak_frames,
                        "pause_frames": p_pause_frames,
                        "segments": p["segments_count"]
                    })
                    
                segment_schedule: List[int] = []
                for entry in phrase_timeline:
                    sf = entry["speak_frames"]
                    pf = entry["pause_frames"]
                    segs = entry["segments"]
                    if sf > 0:
                        segs_per_f = segs / sf
                        accum = 0.0
                        for _ in range(sf):
                            accum += segs_per_f
                            int_segs = int(accum)
                            segment_schedule.append(int_segs)
                            accum -= int_segs
                    else:
                        segment_schedule.append(segs)
                    for _ in range(pf):
                        segment_schedule.append(0)
                        
                if len(segment_schedule) < drawing_outline_frames:
                    segment_schedule.extend([0] * (drawing_outline_frames - len(segment_schedule)))
                elif len(segment_schedule) > drawing_outline_frames:
                    segment_schedule = segment_schedule[:drawing_outline_frames]
                    
                renderer = DrawingRenderer(
                    resolution=resolution,
                    bg_style=bg_style,
                    pen_style=actual_pen_style,
                    pen_color=pen_color,
                    pen_width=pen_width,
                    pen_opacity=pen_opacity,
                    hand_img_path=hand_img_path,
                    camera_enabled=camera_enabled
                )
                
                outline_canvas = Image.new("RGBA", resolution, (0, 0, 0, 0))
                outline_draw = ImageDraw.Draw(outline_canvas)
                
                reveal_mask = Image.new("L", resolution, 0)
                reveal_draw = ImageDraw.Draw(reveal_mask)
                
                proj_grid = None
                W, H = resolution
                L = math.hypot(W, H)
                if scene_color_style in ["diagonal_l2r", "diagonal_r2l", "straight_l2r", "straight_r2l", "straight_t2b", "straight_b2t"]:
                    grid_x, grid_y = np.meshgrid(np.arange(W), np.arange(H))
                    if scene_color_style == "diagonal_l2r":
                        proj_grid = (grid_x * W + grid_y * H) / (W**2 + H**2)
                    elif scene_color_style == "diagonal_r2l":
                        proj_grid = (W**2 - grid_x * W + grid_y * H) / (W**2 + H**2)
                    elif scene_color_style == "straight_l2r":
                        proj_grid = grid_x / W
                    elif scene_color_style == "straight_r2l":
                        proj_grid = (W - grid_x) / W
                    elif scene_color_style == "straight_t2b":
                        proj_grid = grid_y / H
                    elif scene_color_style == "straight_b2t":
                        proj_grid = (H - grid_y) / H
                        
                scene_video_path = os.path.join(dirs["temp"], f"scene_{scene_num}_silent.mp4")
                video_writer = VideoRenderer(scene_video_path, fps=fps, resolution=resolution)
                
                coloring_points = []
                if color_active:
                    coloring_points = renderer.generate_coloring_paths(contours, resolution)
                    
                current_segment_idx = 0
                current_hand_pos = (resolution[0] / 2, resolution[1] / 2)
                
                # --- OUTLINE PHASE ---
                def update_reveal_mask_outline():
                    nonlocal reveal_mask, reveal_draw
                    if color_active and color_option.lower() == "outline and color":
                        reveal_mask = Image.new("L", resolution, 0)
                        reveal_draw = ImageDraw.Draw(reveal_mask)
                        
                        if current_segment_idx < len(segment_to_contour_idx):
                            curr_c_idx = segment_to_contour_idx[current_segment_idx]
                        else:
                            curr_c_idx = len(contours)
                            
                        for i in range(curr_c_idx):
                            c = contours[i]
                            if len(c) > 2:
                                reveal_draw.polygon([tuple(p) for p in c], fill=255)
                            reveal_draw.line([tuple(p) for p in c], fill=255, width=80)
                            
                        if curr_c_idx < len(contours):
                            for s_idx in range(len(all_segments)):
                                if segment_to_contour_idx[s_idx] == curr_c_idx and s_idx < current_segment_idx:
                                    pt1, pt2 = all_segments[s_idx]
                                    reveal_draw.line([pt1, pt2], fill=255, width=80)

                drawing_angle = 0.0
                outline_frames_written = 0
                drawing_frame_idx = 0
                
                while outline_frames_written < outline_frames:
                    if self._check_pause_and_cancel():
                        video_writer.release()
                        finished_cb(False, "Đã hủy bỏ tiến trình.")
                        return
                        
                    segs_to_draw = 0
                    if drawing_frame_idx < len(segment_schedule):
                        is_draw_frame = (segment_schedule[drawing_frame_idx] > 0)
                        if is_draw_frame:
                            remaining_draw_frames = sum(1 for x in segment_schedule[drawing_frame_idx:] if x > 0)
                            if remaining_draw_frames > 0:
                                segs_to_draw = math.ceil((total_segments - current_segment_idx) / remaining_draw_frames)
                            else:
                                segs_to_draw = total_segments - current_segment_idx
                        else:
                            segs_to_draw = 0
                            
                    if current_segment_idx < total_segments and segs_to_draw > 0:
                        next_pt1, next_pt2 = all_segments[current_segment_idx]
                        dist = math.hypot(next_pt1[0] - current_hand_pos[0], next_pt1[1] - current_hand_pos[1])
                        if dist > 20.0 and current_segment_idx > 0:
                            rem_frames = outline_frames - outline_frames_written
                            transition_steps = min(steps_per_jump, rem_frames)
                            if transition_steps > 0:
                                jump_start = current_hand_pos
                                jump_end = next_pt1
                                dx_j = jump_end[0] - jump_start[0]
                                dy_j = jump_end[1] - jump_start[1]
                                jump_angle = math.atan2(dy_j, dx_j)
                                for step in range(1, transition_steps + 1):
                                    if self._check_pause_and_cancel():
                                        video_writer.release()
                                        finished_cb(False, "Đã hủy bỏ tiến trình.")
                                        return
                                    t_j = step / float(transition_steps)
                                    t_eased = t_j * t_j * (3.0 - 2.0 * t_j)
                                    hover_x = jump_start[0] + dx_j * t_eased
                                    hover_y = jump_start[1] + dy_j * t_eased
                                    hover_pos = (hover_x, hover_y)
                                    update_reveal_mask_outline()
                                    bgr_frame = renderer.render_frame(
                                        outline_canvas=outline_canvas,
                                        color_canvas_pil=color_canvas_pil,
                                        reveal_mask=reveal_mask,
                                        current_pt=hover_pos,
                                        color_option=color_option,
                                        target_zoom=1.0,
                                        drawing_angle=jump_angle
                                    )
                                    bgr_frame_logo = overlay_logos(bgr_frame, logos)
                                    video_writer.write_frame(bgr_frame_logo)
                                    outline_frames_written += 1
                                    
                                    if outline_frames_written % 2 == 0:
                                        preview_img = Image.fromarray(cv2.cvtColor(bgr_frame_logo, cv2.COLOR_BGR2RGBA))
                                        preview_cb(preview_img)
                                        
                                    scene_frac = outline_frames_written / total_frames
                                    overall_frac = (idx / total_scenes) * 0.9 + (0.1 / total_scenes) + (scene_frac * 0.75 / total_scenes)
                                    elapsed = time.time() - start_time
                                    if overall_frac > 0:
                                        total_est = elapsed / overall_frac
                                        eta = int(total_est - elapsed)
                                        eta_str = f"{eta // 60:02d}:{eta % 60:02d}"
                                    else:
                                        eta_str = "--:--"
                                    progress_cb(overall_frac, f"Cảnh {scene_num}/{total_scenes}: Đang vẽ nét (Khung hình {outline_frames_written}/{total_frames}) - ETA: {eta_str}")
                                current_hand_pos = next_pt1
                                
                    if outline_frames_written >= outline_frames:
                        break
                        
                    drawing_active = False
                    last_pt1, last_pt2 = None, None
                    for _ in range(segs_to_draw):
                        if current_segment_idx < total_segments:
                            pt1, pt2 = all_segments[current_segment_idx]
                            Brush.draw_segment(
                                outline_draw,
                                pt1,
                                pt2,
                                style=actual_pen_style,
                                color=pen_color,
                                base_width=pen_width,
                                opacity=pen_opacity
                            )
                            last_pt1, last_pt2 = pt1, pt2
                            current_hand_pos = pt2
                            current_segment_idx += 1
                            drawing_active = True
                            
                            if color_active and color_option.lower() == "outline and color":
                                # Sweep color completely from the start of the drawing direction to the current hand coordinate
                                hx, hy = pt2
                                if draw_direction == "left_to_right":
                                    reveal_draw.rectangle([0, 0, int(hx), H], fill=255)
                                elif draw_direction == "right_to_left":
                                    reveal_draw.rectangle([int(hx), 0, W, H], fill=255)
                                elif draw_direction == "top_to_bottom":
                                    reveal_draw.rectangle([0, 0, W, int(hy)], fill=255)
                                elif draw_direction == "bottom_to_top":
                                    reveal_draw.rectangle([0, int(hy), W, H], fill=255)
                                else:
                                    reveal_draw.ellipse(
                                        [pt2[0] - pen_width*6, pt2[1] - pen_width*6, pt2[0] + pen_width*6, pt2[1] + pen_width*6],
                                        fill=255
                                    )
                            
                    if drawing_active and last_pt1 is not None and last_pt2 is not None:
                        dx = last_pt2[0] - last_pt1[0]
                        dy = last_pt2[1] - last_pt1[1]
                        if dx != 0 or dy != 0:
                            drawing_angle = math.atan2(dy, dx)
                            
                    hand_overlay_pos = current_hand_pos
                    target_zoom = 1.35 if drawing_active and camera_enabled else 1.0
                    
                    update_reveal_mask_outline()
                    bgr_frame = renderer.render_frame(
                        outline_canvas=outline_canvas,
                        color_canvas_pil=color_canvas_pil,
                        reveal_mask=reveal_mask,
                        current_pt=hand_overlay_pos,
                        color_option=color_option,
                        target_zoom=target_zoom,
                        drawing_angle=drawing_angle
                    )
                    bgr_frame_logo = overlay_logos(bgr_frame, logos)
                    video_writer.write_frame(bgr_frame_logo)
                    outline_frames_written += 1
                    drawing_frame_idx += 1
                    
                    if outline_frames_written % 2 == 0:
                        preview_img = Image.fromarray(cv2.cvtColor(bgr_frame_logo, cv2.COLOR_BGR2RGBA))
                        preview_cb(preview_img)
                        
                    scene_frac = outline_frames_written / total_frames
                    overall_frac = (idx / total_scenes) * 0.9 + (0.1 / total_scenes) + (scene_frac * 0.75 / total_scenes)
                    elapsed = time.time() - start_time
                    if overall_frac > 0:
                        total_est = elapsed / overall_frac
                        eta = int(total_est - elapsed)
                        eta_str = f"{eta // 60:02d}:{eta % 60:02d}"
                    else:
                        eta_str = "--:--"
                    progress_cb(overall_frac, f"Cảnh {scene_num}/{total_scenes}: Đang vẽ nét (Khung hình {outline_frames_written}/{total_frames}) - ETA: {eta_str}")
                    
                # --- COLORING PHASE ---
                if color_active and (outline_then_color or only_color) and color_frames > 0:
                    centroids = []
                    valid_contours = []
                    for c in contours:
                        if len(c) > 0:
                            centroids.append(np.mean(c, axis=0))
                            valid_contours.append(c)
                            
                    N = len(valid_contours)
                    
                    for f in range(color_frames):
                        if self._check_pause_and_cancel():
                            video_writer.release()
                            finished_cb(False, "Đã hủy bỏ tiến trình.")
                            return
                            
                        t = (f + 1) / color_frames
                        outline_opacity = 1.0 if t < 0.5 else max(0.0, 2.0 * (1.0 - t))
                        
                        # Determine current contour index to paint
                        idx_c = N * (f / color_frames)
                        curr_idx = int(idx_c)
                        frac = idx_c - curr_idx
                        
                        # 1. Determine hand position (needed for camera tracking and hand overlay)
                        if N > 0:
                            target_idx = min(curr_idx, N - 1)
                            c_curr = centroids[target_idx]
                            if curr_idx > 0:
                                c_prev = centroids[curr_idx - 1]
                            else:
                                c_prev = current_hand_pos
                                
                            # Interpolate hand position
                            hand_x = c_prev[0] + (c_curr[0] - c_prev[0]) * frac
                            hand_y = c_prev[1] + (c_curr[1] - c_prev[1]) * frac
                            
                            # Add coloring wiggle
                            freq = 15.0
                            wiggle_r = 20.0
                            wiggle_angle = t * 2.0 * math.pi * freq
                            x_pen = hand_x + wiggle_r * math.cos(wiggle_angle)
                            y_pen = hand_y + wiggle_r * math.sin(wiggle_angle)
                            
                            x_pen = max(0.0, min(x_pen, float(W)))
                            y_pen = max(0.0, min(y_pen, float(H)))
                            current_pt = (x_pen, y_pen)
                            drawing_angle = wiggle_angle + math.pi/2
                        else:
                            current_pt = current_hand_pos
                            drawing_angle = 0.0
                            
                        # 2. Build the reveal mask based on Contour-based reveal (logic gốc)
                        if N > 0:
                            reveal_mask = Image.new("L", resolution, 0)
                            reveal_draw = ImageDraw.Draw(reveal_mask)
                            
                            # Fully reveal all completed contours
                            for i in range(curr_idx):
                                c = valid_contours[i]
                                if len(c) > 2:
                                    p_start = c[0]
                                    p_end = c[-1]
                                    dist = math.hypot(p_start[0] - p_end[0], p_start[1] - p_end[1])
                                    if dist < 800.0:  # Tăng ngưỡng điền polygon lên 800.0 để lấp đầy tốt hơn
                                        reveal_draw.polygon([tuple(p) for p in c], fill=255)
                                reveal_draw.line([tuple(p) for p in c], fill=255, width=120)
                                
                            # Partially reveal current contour
                            if curr_idx < N:
                                c_pts = valid_contours[curr_idx]
                                num_c_reveal = int(len(c_pts) * frac)
                                if num_c_reveal > 1:
                                    reveal_draw.line([tuple(p) for p in c_pts[:num_c_reveal]], fill=255, width=120)
                                    
                            # Apply Morphological Close and Dilate on full resolution (1920x1080) to fill gaps on the object and eliminate white regions
                            mask_np = np.array(reveal_mask)
                            # Close kernel of 240x240 MORPH_RECT joins close contours (filling inner body parts like vest/chair) - extremely fast!
                            kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (240, 240))
                            mask_np = cv2.morphologyEx(mask_np, cv2.MORPH_CLOSE, kernel_close)
                            
                            # Dilate kernel of 40x40 MORPH_ELLIPSE expands the stroke color slightly to ensure smooth, rounded boundaries
                            kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (40, 40))
                            mask_np = cv2.dilate(mask_np, kernel_dilate)
                            reveal_mask = Image.fromarray(mask_np)
                        else:
                            reveal_mask = Image.new("L", resolution, int(255 * t))
                            
                        # Render frame
                        bgr_frame = renderer.render_frame(
                            outline_canvas=outline_canvas,
                            color_canvas_pil=color_canvas_pil,
                            reveal_mask=reveal_mask,
                            current_pt=current_pt,
                            color_option=color_option,
                            target_zoom=1.2 if camera_enabled else 1.0,
                            drawing_angle=drawing_angle,
                            outline_opacity=outline_opacity
                        )
                        bgr_frame_logo = overlay_logos(bgr_frame, logos)
                        video_writer.write_frame(bgr_frame_logo)
                        
                        if f % 2 == 0:
                            preview_img = Image.fromarray(cv2.cvtColor(bgr_frame_logo, cv2.COLOR_BGR2RGBA))
                            preview_cb(preview_img)
                            
                        overall_f = outline_frames_written + f
                        scene_frac = overall_f / total_frames
                        overall_frac = (idx / total_scenes) * 0.9 + (0.1 / total_scenes) + (scene_frac * 0.75 / total_scenes)
                        elapsed = time.time() - start_time
                        if overall_frac > 0:
                            total_est = elapsed / overall_frac
                            eta = int(total_est - elapsed)
                            eta_str = f"{eta // 60:02d}:{eta % 60:02d}"
                        else:
                            eta_str = "--:--"
                        progress_cb(overall_frac, f"Cảnh {scene_num}/{total_scenes}: Đang tô màu (Khung hình {overall_f + 1}/{total_frames}) - ETA: {eta_str}")
                        
                # Write final freeze frames (with transition padding t_next included)
                if color_active:
                    reveal_mask = Image.new("L", resolution, 255)
                    
                bgr_frame = renderer.render_frame(
                    outline_canvas=outline_canvas,
                    color_canvas_pil=color_canvas_pil,
                    reveal_mask=reveal_mask,
                    current_pt=None,
                    color_option=color_option,
                    target_zoom=1.0,
                    outline_opacity=0.0 if color_active else 1.0
                )
                bgr_frame_logo = overlay_logos(bgr_frame, logos)
                
                final_frames_count = total_frames - outline_frames_written - color_frames
                if final_frames_count < 1:
                    final_frames_count = 1
                    
                for _ in range(final_frames_count):
                    video_writer.write_frame(bgr_frame_logo)
                    
                video_writer.release()
                last_frame_prev_scene = bgr_frame_logo
                scene_videos.append(scene_video_path)
                video_durations.append(total_frames / fps)
                scene_numbers.append(scene_num)
                
            if self._check_pause_and_cancel():
                finished_cb(False, "Đã hủy bỏ tiến trình.")
                return
                
            if export_mode == "scenes":
                progress_cb(0.95, "Đang lồng âm thanh, nhạc nền cho từng cảnh và xuất video...")
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                success = True
                failed_scenes = []
                
                for idx in range(len(scene_videos)):
                    if self._check_pause_and_cancel():
                        finished_cb(False, "Đã hủy bỏ tiến trình.")
                        return
                    
                    s_num = scene_numbers[idx]
                    scene_video_path = scene_videos[idx]
                    scene_duration = video_durations[idx]
                    scene_voice_path = scene_audios[idx] if mode != "video_only" and idx < len(scene_audios) else None
                    
                    output_filename = f"drawing_video_{timestamp}-canh{s_num}.mp4"
                    final_output_path = os.path.join(export_dir, output_filename)
                    
                    logger.info(f"Merging scene {s_num} to {final_output_path}")
                    scene_success = AudioMerger.merge(
                        video_path=scene_video_path,
                        voice_path=scene_voice_path,
                        music_path=music_path if music_path else None,
                        output_path=final_output_path,
                        duration=scene_duration,
                        voice_volume=voice_volume,
                        music_volume=music_volume,
                        fade_in=fade_in,
                        fade_out=fade_out
                    )
                    if not scene_success:
                        success = False
                        failed_scenes.append(s_num)
                        
                clean_temp_dir()
                
                if success:
                    logger.info(f"Render completed. Individual scene videos exported to: {export_dir}")
                    progress_cb(1.0, "Hoàn thành!")
                    finished_cb(True, f"Các video từng cảnh đã được lưu thành công tại:\n{export_dir}")
                else:
                    finished_cb(False, f"Lỗi khi lồng tiếng và nhạc nền bằng FFmpeg ở các cảnh: {failed_scenes}")
            else:
                # Step 4: Concatenate video scenes with transitions
                progress_cb(0.92, "Đang ghép nối các phân đoạn video...")
                final_silent_path = os.path.join(dirs["temp"], "final_silent.mp4")
                scene_transitions = [s.get("transition", "none") for s in scenes[1:]]
                if not AudioMerger.concatenate_videos_with_transitions(
                    video_parts=scene_videos,
                    durations=video_durations,
                    transitions=scene_transitions,
                    transition_duration=0.5,
                    output_path=final_silent_path
                ):
                    finished_cb(False, "Không thể ghép các file video phân đoạn.")
                    return
                    
                # Concatenate voice audios
                final_voice_path = ""
                if mode != "video_only":
                    progress_cb(0.94, "Đang ghép nối các file âm thanh voice...")
                    final_voice_path = os.path.join(dirs["temp"], "final_voice.mp3")
                    if len(scene_audios) == 1:
                        import shutil
                        shutil.copy(scene_audios[0], final_voice_path)
                    else:
                        try:
                            with open(final_voice_path, "wb") as outfile:
                                for va in scene_audios:
                                    with open(va, "rb") as infile:
                                        outfile.write(infile.read())
                        except Exception as e:
                            voice_list_file = os.path.join(dirs["temp"], "voice_list.txt")
                            with open(voice_list_file, "w", encoding="utf-8") as f:
                                for va in scene_audios:
                                    f.write(f"file '{os.path.basename(va)}'\n")
                            concat_voice_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", voice_list_file, "-c", "copy", final_voice_path]
                            subprocess.run(concat_voice_cmd, cwd=dirs["temp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, creationflags=creation_flags)
                            if os.path.exists(voice_list_file):
                                os.remove(voice_list_file)
                            
                if self._check_pause_and_cancel():
                    finished_cb(False, "Đã hủy bỏ tiến trình.")
                    return
                    
                # Step 5: Final multiplex merge
                progress_cb(0.97, "Đang lồng âm thanh, nhạc nền và xuất video...")
                if mode == "video_only":
                    total_duration = EdgeTTSGenerator.get_audio_duration(final_silent_path)
                else:
                    total_duration = sum(EdgeTTSGenerator.get_audio_duration(va) for va in scene_audios)
                
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_filename = f"drawing_video_{timestamp}.mp4"
                final_output_path = os.path.join(export_dir, output_filename)
                
                success = AudioMerger.merge(
                    video_path=final_silent_path,
                    voice_path=final_voice_path if mode != "video_only" else None,
                    music_path=music_path if music_path else None,
                    output_path=final_output_path,
                    duration=total_duration,
                    voice_volume=voice_volume,
                    music_volume=music_volume,
                    fade_in=fade_in,
                    fade_out=fade_out
                )
                
                clean_temp_dir()
                
                if success:
                    logger.info(f"Render completed. Video exported to: {final_output_path}")
                    progress_cb(1.0, "Hoàn thành!")
                    finished_cb(True, f"Video đã được lưu thành công tại:\n{final_output_path}")
                else:
                    finished_cb(False, "Lỗi khi lồng tiếng và nhạc nền bằng FFmpeg.")
                
        except Exception as e:
            logger.exception("An error occurred during pipeline execution:")
            clean_temp_dir()
            finished_cb(False, f"Lỗi tiến trình: {str(e)}")
