"""Writes albums out as real folders — by COPYING. Originals are never moved or changed.

Flow: preview (nothing happens on disk) -> apply (copies + logs every file it created) -> undo
(deletes only the copies this export created, if they're unchanged).
"""

import json
import re
import shutil
from pathlib import Path

from .db import connect

UNSORTED = "Unsorted"


def _safe(name: str) -> str:
    """Turn an album name into a valid Windows folder name."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "Album"


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_dest(dest: str) -> Path:
    path = Path(dest.strip().strip('"')).expanduser()
    if not path.is_absolute():
        raise ValueError("Please use a full path, like D:\\Sorted Photos")
    path = path.resolve()
    with connect() as conn:
        folders = [Path(r["path"]) for r in conn.execute("SELECT path FROM folders")]
    for f in folders:
        if _is_inside(path, f):
            raise ValueError(f"The export folder can't be inside a library folder ({f}). Pick a different place.")
    return path


def plan(dest: str, include_unsorted: bool) -> dict:
    root = validate_dest(dest)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT i.id, i.path, i.size, a.name AS album
            FROM images i
            LEFT JOIN album_images ai ON ai.image_id = i.id
            LEFT JOIN albums a ON a.id = ai.album_id
            ORDER BY album, i.path
            """
        ).fetchall()

    taken: set[str] = set()
    items, per_album = [], {}
    for r in rows:
        album = r["album"] or (UNSORTED if include_unsorted else None)
        if album is None:
            continue
        folder = root / _safe(album)
        src = Path(r["path"])
        dst = folder / src.name
        n = 1
        # Never overwrite: add _1, _2, ... if the name is already used (on disk or in this plan).
        while str(dst).lower() in taken or dst.exists():
            dst = folder / f"{src.stem}_{n}{src.suffix}"
            n += 1
        taken.add(str(dst).lower())
        items.append({"src": str(src), "dst": str(dst), "size": r["size"]})
        per_album[album] = per_album.get(album, 0) + 1

    return {
        "dest": str(root),
        "total": len(items),
        "bytes": sum(i["size"] for i in items),
        "folders": [{"name": k, "count": v} for k, v in sorted(per_album.items(), key=lambda kv: -kv[1])],
        "items": items,
    }


def apply(dest: str, include_unsorted: bool) -> dict:
    p = plan(dest, include_unsorted)
    created, failed = [], []
    for item in p["items"]:
        dst = Path(item["dst"])
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["src"], dst)
            created.append({"dst": str(dst), "size": dst.stat().st_size})
        except OSError as e:
            failed.append({"src": item["src"], "error": str(e)})

    with connect() as conn:
        export_id = conn.execute(
            "INSERT INTO exports (dest, files) VALUES (?, ?)", (p["dest"], json.dumps(created))
        ).lastrowid
    return {"id": export_id, "dest": p["dest"], "copied": len(created), "failed": failed}


def undo(export_id: int) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT files, undone FROM exports WHERE id = ?", (export_id,)).fetchone()
    if not row:
        raise ValueError("Export not found")
    if row["undone"]:
        raise ValueError("This export was already undone")

    removed, kept = 0, 0
    dirs: set[Path] = set()
    for f in json.loads(row["files"]):
        path = Path(f["dst"])
        # Only delete a copy if it still looks exactly like what we wrote.
        if path.is_file() and path.stat().st_size == f["size"]:
            path.unlink()
            removed += 1
            dirs.add(path.parent)
        else:
            kept += 1
    for d in dirs:
        try:
            d.rmdir()  # only succeeds if the folder is now empty
        except OSError:
            pass

    with connect() as conn:
        conn.execute("UPDATE exports SET undone = 1 WHERE id = ?", (export_id,))
    return {"removed": removed, "kept": kept}
