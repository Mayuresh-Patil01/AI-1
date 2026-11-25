"""Writes albums out as real folders — by COPYING. Originals are never moved or changed.

Flow: preview (nothing happens on disk) -> apply (copies + logs every file it created) -> undo
(deletes only the copies this export created, if they're unchanged).
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .db import connect

UNSORTED = "Unsorted"

# Folder naming templates. Use "/" to make sub-folders, e.g. "{year}/{album}" -> 2025\Beaches\photo.jpg
TEMPLATE_TOKENS = {
    "album": "Album name",
    "year": "Year the photo was taken, e.g. 2025",
    "month": "Month number, e.g. 07",
    "month_name": "Month name, e.g. July",
    "day": "Day of month, e.g. 04",
    "folder": "Name of the folder the photo came from",
}
DEFAULT_TEMPLATE = "{album}"


def validate_template(template: str) -> str:
    template = template.strip().strip("/\\") or DEFAULT_TEMPLATE
    unknown = set(re.findall(r"\{(\w*)\}", template)) - set(TEMPLATE_TOKENS)
    if unknown:
        raise ValueError(f"Unknown template field: {{{sorted(unknown)[0]}}}. Use: " + ", ".join(f"{{{t}}}" for t in TEMPLATE_TOKENS))
    if "{" not in template:
        raise ValueError("The template needs at least one field, like {album}")
    return template


def render_template(template: str, album: str, taken: datetime, source: Path) -> list[str]:
    """Turn a template into a list of safe folder names (one per sub-folder level)."""
    values = {
        "album": album,
        "year": f"{taken.year}",
        "month": f"{taken.month:02d}",
        "month_name": taken.strftime("%B"),
        "day": f"{taken.day:02d}",
        "folder": source.parent.name,
    }
    rendered = template.format(**values)
    return [_safe(part) for part in re.split(r"[\\/]+", rendered) if part.strip()]


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


def plan(dest: str, include_unsorted: bool, template: str = DEFAULT_TEMPLATE) -> dict:
    root = validate_dest(dest)
    template = validate_template(template)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT i.id, i.path, i.size, i.mtime, i.taken_at, a.name AS album
            FROM images i
            LEFT JOIN album_images ai ON ai.image_id = i.id
            LEFT JOIN albums a ON a.id = ai.album_id
            ORDER BY album, i.path
            """
        ).fetchall()

    taken: set[str] = set()
    items, per_folder = [], {}
    for r in rows:
        album = r["album"] or (UNSORTED if include_unsorted else None)
        if album is None:
            continue
        src = Path(r["path"])
        # Date the photo was taken (from EXIF), or else when the file was last modified.
        when = datetime.fromisoformat(r["taken_at"]) if r["taken_at"] else datetime.fromtimestamp(r["mtime"])
        parts = render_template(template, album, when, src)
        folder = root.joinpath(*parts)
        dst = folder / src.name
        n = 1
        # Never overwrite: add _1, _2, ... if the name is already used (on disk or in this plan).
        while str(dst).lower() in taken or dst.exists():
            dst = folder / f"{src.stem}_{n}{src.suffix}"
            n += 1
        taken.add(str(dst).lower())
        items.append({"src": str(src), "dst": str(dst), "size": r["size"]})
        label = "\\".join(parts)
        per_folder[label] = per_folder.get(label, 0) + 1

    return {
        "dest": str(root),
        "template": template,
        "total": len(items),
        "bytes": sum(i["size"] for i in items),
        "folders": [{"name": k, "count": v} for k, v in sorted(per_folder.items(), key=lambda kv: -kv[1])],
        "items": items,
    }


def apply(dest: str, include_unsorted: bool, template: str = DEFAULT_TEMPLATE) -> dict:
    p = plan(dest, include_unsorted, template)
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
        row = conn.execute("SELECT dest, files, undone FROM exports WHERE id = ?", (export_id,)).fetchone()
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
    # Remove folders the export created if they're now empty, walking up (e.g. 2025\Beaches, then 2025),
    # but never above the export folder itself.
    root = Path(row["dest"])
    for d in sorted(dirs, key=lambda p: -len(p.parts)):
        while d != root and _is_inside(d, root):
            try:
                d.rmdir()  # only succeeds if the folder is empty
            except OSError:
                break
            d = d.parent

    with connect() as conn:
        conn.execute("UPDATE exports SET undone = 1 WHERE id = ?", (export_id,))
    return {"removed": removed, "kept": kept}
