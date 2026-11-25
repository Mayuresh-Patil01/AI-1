"""Finds images inside a folder and records them in the database.

Rescans are incremental: a file is only re-read if its size or modified time changed.
Original files are only ever READ here, never changed.
"""

from datetime import datetime
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

from .config import IMAGE_EXTENSIONS
from .db import connect

register_heif_opener()  # lets Pillow open .HEIC files

EXIF_DATETIME_ORIGINAL = 36867  # EXIF tag: when the photo was taken
EXIF_IFD = 0x8769               # EXIF sub-section that holds that tag


def read_image_info(path: Path) -> dict:
    """Return width, height and date taken. Never raises: bad files just get None values."""
    info = {"width": None, "height": None, "taken_at": None}
    try:
        with Image.open(path) as img:
            info["width"], info["height"] = img.size
            raw = img.getexif().get_ifd(EXIF_IFD).get(EXIF_DATETIME_ORIGINAL)
            if raw:
                # EXIF dates look like "2025:12:24 18:30:05"
                info["taken_at"] = datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S").isoformat()
    except Exception:
        pass
    return info


def scan_folder(folder_id: int, folder_path: str) -> dict:
    """Walk the folder (including subfolders) and sync the images table with what's on disk."""
    root = Path(folder_path)
    added = updated = unchanged = 0
    seen: set[str] = set()

    with connect() as conn:
        known = {
            row["path"]: (row["size"], row["mtime"])
            for row in conn.execute("SELECT path, size, mtime FROM images WHERE folder_id = ?", (folder_id,))
        }

        for file in root.rglob("*"):
            if not file.is_file() or file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            path = str(file)
            seen.add(path)
            stat = file.stat()

            if known.get(path) == (stat.st_size, stat.st_mtime):
                unchanged += 1
                continue

            info = read_image_info(file)
            conn.execute(
                """
                INSERT INTO images (folder_id, path, size, mtime, width, height, taken_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    size = excluded.size, mtime = excluded.mtime, width = excluded.width,
                    height = excluded.height, taken_at = excluded.taken_at
                """,
                (folder_id, path, stat.st_size, stat.st_mtime, info["width"], info["height"], info["taken_at"]),
            )
            if path in known:
                updated += 1
                # The photo changed, so its old AI fingerprint is stale.
                conn.execute("DELETE FROM embeddings WHERE image_id = (SELECT id FROM images WHERE path = ?)", (path,))
            else:
                added += 1

        # Files that disappeared from disk are removed from the library (not from disk!).
        gone = [p for p in known if p not in seen]
        conn.executemany("DELETE FROM images WHERE path = ?", [(p,) for p in gone])

    return {"added": added, "updated": updated, "unchanged": unchanged, "removed": len(gone)}
