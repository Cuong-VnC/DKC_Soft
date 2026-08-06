import os
import shutil
import tempfile
from PIL import Image, ImageDraw

def get_workspace_dir() -> str:
    """Returns the base project workspace directory."""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.abspath(os.path.dirname(sys.executable))
    return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def ensure_directories() -> dict:
    """Ensures base project folders exist and returns their paths."""
    base = get_workspace_dir()
    dirs = {
        "assets": os.path.join(base, "assets"),
        "brushes": os.path.join(base, "assets", "brushes"),
        "backgrounds": os.path.join(base, "assets", "backgrounds"),
        "projects": os.path.join(base, "projects"),
        "output": os.path.join(base, "output"),
        "temp": os.path.join(base, "temp")
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    return dirs

def clean_temp_dir() -> None:
    """Cleans up the temp folder safely with retry logic to handle file locks."""
    temp_dir = os.path.join(get_workspace_dir(), "temp")
    if not os.path.exists(temp_dir):
        return
        
    import time
    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        # Try to delete file with retry to handle files locked by ffmpeg/other processes
        for attempt in range(3):
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
                break
            except PermissionError:
                time.sleep(0.2)
            except Exception:
                break

def get_short_path_name(long_name: str) -> str:
    """
    Gets the short path name of a path on Windows.
    This is extremely useful for libraries like OpenCV (cv2.imread, cv2.VideoWriter)
    which fail with Unicode paths on Windows.
    """
    if os.name != 'nt':
        return long_name
    try:
        import ctypes
        from ctypes import wintypes
        
        # Ensure the parent directory path exists or GetShortPathNameW may fail
        parent_dir = os.path.dirname(long_name)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
            
        buf_size = 256
        gui_buf = ctypes.create_unicode_buffer(buf_size)
        GetShortPathName = ctypes.windll.kernel32.GetShortPathNameW
        GetShortPathName.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        GetShortPathName.restype = wintypes.DWORD
        
        # Try direct conversion first
        needed = GetShortPathName(long_name, gui_buf, buf_size)
        if needed > 0:
            if needed > buf_size:
                gui_buf = ctypes.create_unicode_buffer(needed)
                GetShortPathName(long_name, gui_buf, needed)
            if gui_buf.value:
                return gui_buf.value
                
        # If direct conversion failed (e.g. file doesn't exist yet),
        # convert the parent directory to short path and append the base name
        if parent_dir:
            needed = GetShortPathName(parent_dir, gui_buf, buf_size)
            if needed > 0:
                if needed > buf_size:
                    gui_buf = ctypes.create_unicode_buffer(needed)
                    GetShortPathName(parent_dir, gui_buf, needed)
                if gui_buf.value:
                    return os.path.join(gui_buf.value, os.path.basename(long_name))
    except Exception:
        pass
    return long_name

def generate_default_hand(filepath: str) -> None:
    """
    Generates a default hand holding a pen PNG image with transparent background.
    The tip of the pen is located exactly at (0, 128) - bottom-left.
    Size: 128x128 pixels.
    """
    # Create transparent image
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw pen barrel: diagonal rectangle from top-right down to bottom-left
    # Tip of the pen is at (0, 128). The pen extends up-right towards (120, 8)
    # Pen line: from (120, 8) to (20, 108)
    pen_color = (40, 40, 40, 255)  # Charcoal
    draw.line([(120, 8), (20, 108)], fill=pen_color, width=12)
    
    # Pen metal tip cone: triangle from (20, 108) along pen axis to tip (0, 128)
    # Cone coordinates: (15, 103), (25, 113), (0, 128)
    tip_color = (200, 200, 200, 255)  # Silver
    draw.polygon([(14, 102), (26, 114), (0, 128)], fill=tip_color)
    
    # Ink nib point
    draw.polygon([(4, 124), (8, 128), (0, 128)], fill=(0, 0, 0, 255))
    
    # Draw Hand holding the pen:
    # A couple of fingers (ellipses) in skin-tone style or soft gray
    hand_color = (240, 200, 180, 255)  # Peach skin tone
    shadow_color = (220, 180, 160, 255)
    
    # Index finger wrapping the pen: centered around (50, 75)
    draw.ellipse([40, 65, 75, 90], fill=hand_color, outline=shadow_color, width=1)
    
    # Thumb pressing the pen: centered around (65, 55)
    draw.ellipse([50, 45, 80, 70], fill=hand_color, outline=shadow_color, width=1)
    
    # Rest of hand/knuckle backing: ellipse from (70, 30) to (110, 80)
    draw.ellipse([70, 30, 115, 85], fill=hand_color)
    
    # Save the hand image
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img.save(filepath, "PNG")

def get_hand_image_path() -> str:
    """Returns the path to the hand image, generating a default one if missing."""
    dirs = ensure_directories()
    hand_path = os.path.join(dirs["assets"], "hand.png")
    if not os.path.exists(hand_path):
        generate_default_hand(hand_path)
    return hand_path
