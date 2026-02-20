"""Resource management utility."""

import os
import sys
from PIL import Image
from typing import Tuple

def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, handling different execution contexts.
    
    Args:
        relative_path: Path relative to the project root (e.g., 'assets/icon.png').
        
    Returns:
        The absolute path to the resource.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def load_pil_image(relative_path: str, fallback_size: Tuple[int, int] = (64, 64)) -> Image.Image:
    """
    Load an image using PIL from a relative path.
    
    Args:
        relative_path: Path relative to the project root.
        fallback_size: Size of the fallback image if the file is not found.
        
    Returns:
        A PIL Image object.
    """
    full_path = get_resource_path(relative_path)
    if os.path.exists(full_path):
        try:
            return Image.open(full_path)
        except Exception as e:
            print(f"Error loading image {full_path}: {e}")
            
    # Return a black fallback image
    return Image.new('RGB', fallback_size, color=(0, 0, 0))
