import asyncio
import os
import re
import subprocess
import logging
from typing import List, Tuple, Dict, Any
import edge_tts
import platform
import random

logger = logging.getLogger("AIDrawingVideo")

creation_flags = 0
if platform.system() == "Windows":
    creation_flags = subprocess.CREATE_NO_WINDOW

class EdgeTTSGenerator:
    def __init__(self):
        # Cached voices list
        self.voices: List[Dict[str, Any]] = []

    async def get_all_voices(self) -> List[Dict[str, Any]]:
        """Fetches and caches the list of available edge-tts voices."""
        if self.voices:
            return self.voices
        try:
            voices_list = await edge_tts.list_voices()
            self.voices = [
                {
                    "Name": v["Name"],
                    "ShortName": v["ShortName"],
                    "Gender": v["Gender"],
                    "Locale": v["Locale"],
                    "FriendlyName": f"{v['Locale']} - {v['ShortName'].split('-')[-1]} ({v['Gender']})"
                }
                for v in voices_list
            ]
            # Sort by locale, then name
            self.voices.sort(key=lambda x: (x["Locale"], x["ShortName"]))
        except Exception as e:
            logger.error(f"Failed to fetch edge-tts voices: {e}")
            # Fallback voices list
            self.voices = [
                {"Name": "Microsoft Server Speech Text to Speech Voice (vi-VN, HoaiMyNeural)", "ShortName": "vi-VN-HoaiMyNeural", "Gender": "Female", "Locale": "vi-VN", "FriendlyName": "vi-VN - HoaiMyNeural (Female)"},
                {"Name": "Microsoft Server Speech Text to Speech Voice (vi-VN, NamMinhNeural)", "ShortName": "vi-VN-NamMinhNeural", "Gender": "Male", "Locale": "vi-VN", "FriendlyName": "vi-VN - NamMinhNeural (Male)"},
                {"Name": "Microsoft Server Speech Text to Speech Voice (en-US, AriaNeural)", "ShortName": "en-US-AriaNeural", "Gender": "Female", "Locale": "en-US", "FriendlyName": "en-US - AriaNeural (Female)"},
                {"Name": "Microsoft Server Speech Text to Speech Voice (en-US, GuyNeural)", "ShortName": "en-US-GuyNeural", "Gender": "Male", "Locale": "en-US", "FriendlyName": "en-US - GuyNeural (Male)"}
            ]
        return self.voices

    def get_all_voices_sync(self) -> List[Dict[str, Any]]:
        """Synchronous wrapper to get voices list."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(self.get_all_voices())
            loop.close()
            return res
        except Exception:
            return [
                {"Name": "vi-VN-HoaiMyNeural", "ShortName": "vi-VN-HoaiMyNeural", "Gender": "Female", "Locale": "vi-VN", "FriendlyName": "vi-VN - HoaiMy (Female)"},
                {"Name": "vi-VN-NamMinhNeural", "ShortName": "vi-VN-NamMinhNeural", "Gender": "Male", "Locale": "vi-VN", "FriendlyName": "vi-VN - NamMinh (Male)"},
                {"Name": "en-US-GuyNeural", "ShortName": "en-US-GuyNeural", "Gender": "Male", "Locale": "en-US", "FriendlyName": "en-US - Guy (Male)"}
            ]

    async def generate_voice(
        self,
        text: str,
        voice: str,
        output_path: str,
        rate: int = 0,
        pitch: int = 0,
        volume: int = 0
    ) -> float:
        """
        Generates TTS speech and saves it as an MP3.
        Returns the duration of the generated audio file.
        """
        # Only pass rate/pitch/volume if they are non-zero to avoid Microsoft server parsing issues
        kwargs = {}
        if rate != 0:
            kwargs["rate"] = f"{rate:+}%"
        if pitch != 0:
            kwargs["pitch"] = f"{pitch:+}Hz"
        if volume != 0:
            kwargs["volume"] = f"{volume:+}%"
            
        max_retries = 10
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating TTS using voice '{voice}' (Lần thử {attempt + 1}/10)...")
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=voice,
                    **kwargs
                )
                await communicate.save(output_path)
                
                # Get audio duration
                duration = self.get_audio_duration(output_path)
                logger.info(f"Generated TTS successfully. Duration: {duration:.2f}s")
                return duration
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Thất bại tạo TTS sau {max_retries} lần thử.")
                    raise e
                
                # Random delay between 2.0 to 5.0 seconds
                delay = random.uniform(2.0, 5.0)
                logger.warning(f"Lỗi tạo TTS ở lần thử {attempt + 1}: {e}. Đang thử lại sau {delay:.2f}s...")
                await asyncio.sleep(delay)

    @staticmethod
    def get_audio_duration(audio_path: str) -> float:
        """
        Checks the duration of an audio file using ffprobe/ffmpeg.
        Returns duration in seconds.
        """
        if not os.path.exists(audio_path):
            return 0.0
            
        try:
            # 1. Try ffprobe
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, creationflags=creation_flags)
            return float(result.stdout.strip())
        except Exception:
            # 2. Try ffmpeg fallback
            try:
                cmd = ["ffmpeg", "-i", audio_path]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
                match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
                if match:
                    hours, minutes, seconds = match.groups()
                    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            except Exception as e:
                logger.error(f"Failed to read audio duration: {e}")
                
        # Estimate duration by file size (128kbps default edge-tts mp3 quality -> ~16KB/s)
        try:
            size_bytes = os.path.getsize(audio_path)
            return max(1.0, size_bytes / 16000.0)
        except Exception:
            return 10.0

    @staticmethod
    def analyze_punctuation_timing(text: str, total_duration: float) -> List[Dict[str, Any]]:
        """
        Parses text and splits it into phrases by punctuation.
        Allocates relative time weights and pauses for each phrase.
        Returns a list of phrase dicts containing text, duration, and pause duration.
        """
        # Split by sentence-ending punctuation or commas, keeping the punctuation
        # pattern captures text and matching punctuation
        parts = re.split(r"([.,!?;:\n]+)", text)
        
        phrases = []
        current_phrase = ""
        
        for part in parts:
            if not part:
                continue
            if re.match(r"^[.,!?;:\n]+$", part):
                # This is a punctuation mark for the preceding phrase
                if phrases:
                    phrases[-1]["punctuation"] += part
                else:
                    current_phrase += part
            else:
                # This is text
                if current_phrase.strip():
                    phrases.append({
                        "text": current_phrase.strip(),
                        "punctuation": ""
                    })
                current_phrase = part
                
        if current_phrase.strip():
            phrases.append({
                "text": current_phrase.strip(),
                "punctuation": ""
            })
            
        if not phrases:
            return [{
                "text": text,
                "speak_duration": total_duration,
                "duration": total_duration,
                "pause": 0.0,
                "char_count": len(text)
            }]
            
        # Calculate raw weights
        # Comma, colon: 0.2s pause. Period, question, exclamation, newline: 0.5s pause
        total_pause_time = 0.0
        for p in phrases:
            punct = p["punctuation"]
            p["char_count"] = len(p["text"])
            
            if not punct:
                p["pause_type"] = "none"
                p["raw_pause"] = 0.0
            elif any(c in punct for c in [".", "?", "!", "\n"]):
                p["pause_type"] = "long"
                p["raw_pause"] = 0.5
            else:
                p["pause_type"] = "short"
                p["raw_pause"] = 0.25
            total_pause_time += p["raw_pause"]
            
        # If pause time is greater than 60% of total audio duration, compress pauses
        if total_pause_time > total_duration * 0.6:
            scale = (total_duration * 0.4) / max(total_pause_time, 0.001)
            for p in phrases:
                p["raw_pause"] *= scale
            total_pause_time = total_duration * 0.4
            
        # Remaining time is allocated for reading the characters
        speaking_time = total_duration - total_pause_time
        total_chars = sum(p["char_count"] for p in phrases)
        if total_chars == 0:
            total_chars = 1
            
        # Distribute speaking time based on characters
        for p in phrases:
            char_ratio = p["char_count"] / total_chars
            p["speak_duration"] = speaking_time * char_ratio
            p["duration"] = p["speak_duration"]
            p["pause"] = p["raw_pause"]
            
        return phrases
