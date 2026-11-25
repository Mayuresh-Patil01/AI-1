"""Small preview images so the UI grid stays fast, cached on disk."""

import hashlib
from pathlib import Path

from PIL import Image, ImageOps

from .config import THUMB_DIR, THUMB_SIZE


def get_thumbnail(image_path: str, mtime: float, size: int = THUMB_SIZE) -> Path:
    """Return the path to a cached JPEG thumbnail, creating it if needed."""
    # The cache key includes mtime, so an edited photo gets a fresh thumbnail.
    key = hashlib.sha1(f"{image_path}|{mtime}|{size}".encode()).hexdigest()
    thumb = THUMB_DIR / f"{key}.jpg"
    if thumb.exists():
        return thumb

    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)  # respect phone rotation
        img.thumbnail((size, size))
        img.convert("RGB").save(thumb, "JPEG", quality=82)
    return thumb
