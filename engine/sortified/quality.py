"""Cheap, non-AI measurements of each photo: sharpness, brightness and a perceptual hash.

All work on a small grayscale copy, so they're fast even on a CPU.
"""

import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

WORK_SIZE = 512  # analyze at this size so results are comparable across photo resolutions


def _gray(path: str) -> np.ndarray | None:
    try:
        with Image.open(path) as img:
            img.draft("L", (WORK_SIZE, WORK_SIZE))
            img = ImageOps.exif_transpose(img).convert("L")
            img.thumbnail((WORK_SIZE, WORK_SIZE))
            return np.asarray(img, dtype=np.float32)
    except Exception:
        return None


def sharpness(gray: np.ndarray) -> float:
    """Variance of the Laplacian: sharp photos have strong edges (high variance), blurry ones don't."""
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    lap = (
        -4 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1] + gray[2:, 1:-1]
        + gray[1:-1, :-2] + gray[1:-1, 2:]
    )
    return float(lap.var())


def dhash(gray: np.ndarray) -> str:
    """Difference hash: shrink to 9x8, compare each pixel with its right neighbour -> 64 bits.

    Resized, re-saved or slightly edited copies of a photo get (nearly) the same hash.
    """
    small = np.asarray(Image.fromarray(gray.astype(np.uint8)).resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return f"{value:016x}"


def measure(path: str) -> dict | None:
    gray = _gray(path)
    if gray is None:
        return None
    return {"sharpness": sharpness(gray), "brightness": float(gray.mean()), "dhash": dhash(gray)}


def hamming(a: str, b: str) -> int:
    """Number of differing bits between two hashes (0 = identical)."""
    return (int(a, 16) ^ int(b, 16)).bit_count()
