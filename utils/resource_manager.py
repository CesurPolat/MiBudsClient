"""Resource management utility."""

import os
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
    # Assuming this file is in utils/ and the root is one level up
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, relative_path)
    
    # Fallback to current working directory if not found in relative base
    if not os.path.exists(path):
        path = os.path.join(os.getcwd(), relative_path)
        
    return path

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
