import os
import subprocess
import logging
from typing import Optional, List
import platform

logger = logging.getLogger("AIDrawingVideo")

creation_flags = 0
if platform.system() == "Windows":
    creation_flags = subprocess.CREATE_NO_WINDOW

class AudioMerger:
    @staticmethod
    def merge(
        video_path: str,
        voice_path: str,
        music_path: Optional[str],
        output_path: str,
        duration: float,
        voice_volume: float = 1.0,
        music_volume: float = 0.15,
        fade_in: float = 2.0,
        fade_out: float = 3.0
    ) -> bool:
        """
        Merges silent video, voice audio, and background music into a single MP4 H264.
        Applies volume controls and background music fading.
        """
        if not os.path.exists(video_path):
            logger.error(f"Merge error: video file not found at {video_path}")
            return False

        has_voice = voice_path and os.path.exists(voice_path)
        has_music = music_path and os.path.exists(music_path)

        # Build FFmpeg command
        cmd = ["ffmpeg", "-y"]
        
        # Inputs:
        # 0: video
        cmd.extend(["-i", video_path])
        
        filter_complex = ""
        
        if has_voice and has_music:
            cmd.extend(["-i", voice_path])
            cmd.extend(["-stream_loop", "-1", "-i", music_path])
            
            fade_out_start = max(0.0, duration - fade_out)
            filter_complex = (
                f"[1:a]volume={voice_volume}[v_vol];"
                f"[2:a]volume={music_volume},afade=t=in:ss=0:d={fade_in},"
                f"afade=t=out:st={fade_out_start}:d={fade_out}[m_vol];"
                f"[v_vol][m_vol]amix=inputs=2:duration=first:dropout_transition=2[a]"
            )
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[a]"
            ])
        elif has_voice:
            cmd.extend(["-i", voice_path])
            filter_complex = f"[1:a]volume={voice_volume}[a]"
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[a]"
            ])
        elif has_music:
            cmd.extend(["-stream_loop", "-1", "-i", music_path])
            fade_out_start = max(0.0, duration - fade_out)
            filter_complex = (
                f"[1:a]volume={music_volume},afade=t=in:ss=0:d={fade_in},"
                f"afade=t=out:st={fade_out_start}:d={fade_out}[a]"
            )
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[a]"
            ])
        else:
            # Video only, no audio streams
            cmd.extend([
                "-map", "0:v"
            ])
            
        # Output video options: encode to standard H264 (libx264)
        cmd.extend([
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p"
        ])
        if has_voice or has_music:
            cmd.extend([
                "-c:a", "aac",
                "-shortest"  # Stop writing when the shortest stream ends
            ])
        cmd.append(output_path)
        
        logger.info(f"Running FFmpeg merge command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                creationflags=creation_flags
            )
            logger.info("FFmpeg audio-video merge completed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg command failed with return code {e.returncode}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error executing FFmpeg merge: {e}")
            return False
            
    @staticmethod
    def concatenate_videos(video_parts: List[str], output_path: str) -> bool:
        """
        Concatenates multiple video parts into a single video file.
        Useful when rendering multiple images/scripts sequentially.
        """
        if not video_parts:
            return False
        if len(video_parts) == 1:
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(video_parts[0], output_path)
                return True
            except Exception as e:
                logger.error(f"Failed to copy single video part: {e}")
                return False
                
        # Write temporary text file for ffmpeg concat demuxer
        temp_dir = os.path.dirname(output_path)
        list_file = os.path.join(temp_dir, "concat_list.txt")
        
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for vp in video_parts:
                    # Write relative paths to prevent FFmpeg Windows path errors
                    f.write(f"file '{os.path.basename(vp)}'\n")
                    
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                output_path
            ]
            
            logger.info(f"Running Concat FFmpeg: {' '.join(cmd)}")
            # Run command inside temp_dir so relative paths resolve correctly
            subprocess.run(cmd, cwd=temp_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
            
            if os.path.exists(list_file):
                os.remove(list_file)
            logger.info("Multi-part video concatenation completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to concatenate video parts: {e}")
            if os.path.exists(list_file):
                try:
                    os.remove(list_file)
                except Exception:
                    pass
            return False

    @staticmethod
    def concatenate_videos_with_transitions(
        video_parts: List[str],
        durations: List[float],
        transitions: List[str],
        transition_duration: float,
        output_path: str
    ) -> bool:
        """
        Concatenates video parts using xfade filters where specified.
        If no transitions are present or only 1 part exists, it falls back to simple concat.
        """
        if not video_parts:
            return False
            
        has_transitions = any(t != "none" for t in transitions)
        if not has_transitions or len(video_parts) <= 1:
            # Fallback to simple concatenation
            logger.info("No transitions selected or single video part. Using simple concat demuxer.")
            return AudioMerger.concatenate_videos(video_parts, output_path)
            
        temp_dir = os.path.dirname(output_path)
        
        # Build FFmpeg command
        cmd = ["ffmpeg", "-y"]
        for vp in video_parts:
            cmd.extend(["-i", vp])
            
        filter_nodes = []
        last_label = "[0:v]"
        current_time = durations[0]
        
        # Valid FFmpeg xfade transition codes
        XFADE_CODES = [
            "fade", "wipeleft", "wiperight", "wipeup", "wipedown", "slideleft", "slideright",
            "slideup", "slidedown", "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite",
            "radial", "smoothleft", "smoothright", "smoothup", "smoothdown", "circleopen", "circleclose",
            "horzopen", "horzclose", "vertopen", "vertclose", "diagtl", "diagtr", "diagbl", "diagbr",
            "hlslice", "hrslice", "vuslice", "vdslice", "dissolve", "pixelize", "hlwind", "hrwind",
            "vuwind", "vdwind", "hblur", "fadegrays", "squeezeh", "squeezev", "zoomin"
        ]
        
        for i in range(1, len(video_parts)):
            trans_type = transitions[i-1]
            if trans_type == "random":
                import random
                trans_type = random.choice(XFADE_CODES)
                
            # If transition type is not supported or none, default to fade with 0.01 duration (effectively instant)
            if trans_type not in XFADE_CODES or trans_type == "none":
                trans_type = "fade"
                t_dur = 0.01
            else:
                t_dur = transition_duration
                
            # Clamp transition duration to half of either clip length to prevent overflow
            t_dur = min(t_dur, durations[i-1] / 2.0, durations[i] / 2.0)
            
            offset = current_time - t_dur
            next_label = f"[v_link_{i}]"
            
            node = f"{last_label}[{i}:v]xfade=transition={trans_type}:duration={t_dur:.3f}:offset={offset:.3f}{next_label}"
            filter_nodes.append(node)
            
            last_label = next_label
            current_time = current_time + durations[i] - t_dur
            
        filter_complex = ";".join(filter_nodes)
        
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", last_label,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path
        ])
        
        logger.info(f"Running xfade concat FFmpeg command: {' '.join(cmd)}")
        try:
            # Execute command inside temp_dir
            subprocess.run(cmd, cwd=temp_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
            logger.info("Chained xfade transition concatenation completed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg xfade command failed with return code {e.returncode}")
            logger.error(f"FFmpeg stderr: {e.stderr.decode('utf-8', errors='ignore')}")
            return False
        except Exception as e:
            logger.error(f"Failed to concatenate videos with xfade: {e}")
            return False
