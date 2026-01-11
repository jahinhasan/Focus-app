import os
import tkinter as tk
from datetime import datetime

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

class FileHandler:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.temp_dir = os.path.join(os.getcwd(), "temp_uploads")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def check_clipboard(self):
        """
        Check clipboard for:
        1. Image data
        2. File path text
        Returns: (type, content) or (None, None)
        type: 'image_path' | 'file_path' | 'text'
        """
        
        # 1. Try Image
        if ImageGrab:
            try:
                img = ImageGrab.grabclipboard()
                if img:
                    # Save to temp file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_path = os.path.join(self.temp_dir, f"clipboard_image_{timestamp}.png")
                    img.save(temp_path, "PNG")
                    return "image_path", temp_path
            except Exception:
                pass # Not an image or clipboard error

        # 2. Try Text / File Path
        try:
            text = self.root.clipboard_get()
            text = text.strip().strip('"').strip("'") # Clean quotes
            
            # Check if it's a valid local file
            if os.path.exists(text) and os.path.isfile(text):
                return "file_path", text
            
            return "text", text
        except tk.TclError:
            return None, None # Clipboard empty

    def get_file_info(self, path):
        if not os.path.exists(path):
            return None
        return {
            "name": os.path.basename(path),
            "size": os.path.getsize(path),
            "ext": os.path.splitext(path)[1].lower()
        }
