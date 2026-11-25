"""Where SORTIFIED keeps its own data (database, thumbnail cache).

This lives in your user folder, NOT in the git repo, because it can get large
and is specific to each PC.
"""

import os
from pathlib import Path

# Can be overridden with the SORTIFIED_DATA environment variable.
DATA_DIR = Path(os.environ.get("SORTIFIED_DATA", Path.home() / ".sortified"))
DB_PATH = DATA_DIR / "library.db"
THUMB_DIR = DATA_DIR / "thumbnails"

THUMB_SIZE = 400  # longest side of a thumbnail, in pixels

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif",
}

DATA_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR.mkdir(parents=True, exist_ok=True)
