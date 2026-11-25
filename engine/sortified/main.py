"""The local API the UI talks to. Run with:

    .venv\\Scripts\\python -m uvicorn sortified.main:app --reload --port 8000

Then open http://127.0.0.1:8000/docs to try every endpoint in the browser.
"""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__, ai, exporter, jobs, organizer
from .db import connect, get_version, init_db
from .scanner import scan_folder
from .thumbnails import get_thumbnail

app = FastAPI(title="SORTIFIED engine", version=__version__)

# Only the local UI dev server may call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__, "schema": get_version(), "ai": ai.status()}


# ---------------------------------------------------------------- folders

class AddFolderRequest(BaseModel):
    path: str


@app.get("/api/folders")
def list_folders():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT f.id, f.path, COUNT(i.id) AS image_count
            FROM folders f LEFT JOIN images i ON i.folder_id = f.id
            GROUP BY f.id ORDER BY f.added_at
            """
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/folders")
def add_folder(req: AddFolderRequest):
    folder = Path(req.path.strip().strip('"')).expanduser()
    if not folder.is_dir():
        raise HTTPException(400, f"Not a folder: {folder}")
    folder = folder.resolve()

    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO folders (path) VALUES (?)", (str(folder),))
        folder_id = conn.execute("SELECT id FROM folders WHERE path = ?", (str(folder),)).fetchone()["id"]

    result = scan_folder(folder_id, str(folder))
    return {"id": folder_id, "path": str(folder), "scan": result}


@app.post("/api/folders/{folder_id}/rescan")
def rescan_folder(folder_id: int):
    with connect() as conn:
        row = conn.execute("SELECT path FROM folders WHERE id = ?", (folder_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Folder not found")
    return scan_folder(folder_id, row["path"])


@app.delete("/api/folders/{folder_id}")
def remove_folder(folder_id: int):
    """Removes the folder from the library only. Files on disk are untouched."""
    with connect() as conn:
        conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
    return {"removed": folder_id}


# ---------------------------------------------------------------- images

@app.get("/api/images")
def list_images(
    folder_id: int | None = None,
    album_id: int | None = None,
    unsorted: bool = False,
    offset: int = 0,
    limit: int = 200,
):
    conditions, params = [], []
    if folder_id:
        conditions.append("i.folder_id = ?")
        params.append(folder_id)
    if album_id:
        conditions.append("ai.album_id = ?")
        params.append(album_id)
    if unsorted:
        conditions.append("ai.album_id IS NULL")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    base = f"FROM images i LEFT JOIN album_images ai ON ai.image_id = i.id {where}"
    # In an album, show the AI's most confident picks first.
    order = "ai.score DESC, i.path" if album_id else "COALESCE(i.taken_at, '') DESC, i.path"

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT i.id, i.folder_id, i.path, i.size, i.width, i.height, i.taken_at, ai.album_id
            {base} ORDER BY {order} LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    items = [{**dict(r), "name": Path(r["path"]).name} for r in rows]
    return {"total": total, "items": items}


SIZES = {"thumb": 400, "large": 1600}


@app.get("/api/images/{image_id}/thumbnail")
def image_thumbnail(image_id: int, size: str = "thumb"):
    # Looked up by id, so the API can only ever serve files that are in the library.
    if size not in SIZES:
        raise HTTPException(400, f"size must be one of {list(SIZES)}")
    with connect() as conn:
        row = conn.execute("SELECT path, mtime FROM images WHERE id = ?", (image_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Image not found")
    try:
        thumb = get_thumbnail(row["path"], row["mtime"], SIZES[size])
    except Exception:
        raise HTTPException(422, "Could not read this image")
    # "no-cache" = the browser must re-check with us each time (cheap: answered with 304 via the ETag).
    # Image ids can be reused after photos are removed, so long-lived browser caching would show stale pictures.
    return FileResponse(thumb, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- AI organizing

class OrganizeRequest(BaseModel):
    mode: Literal["auto", "custom"] = "auto"
    count: int | None = Field(None, ge=2, le=60)       # auto mode: number of albums (None = decide)
    categories: list[str] = []                         # custom mode: your category names
    strictness: float = Field(0.4, ge=0, le=1)         # custom mode: how sure the AI must be


@app.post("/api/organize")
def start_organize(req: OrganizeRequest):
    categories = list(dict.fromkeys(c.strip() for c in req.categories if c.strip()))  # dedupe, keep order
    if req.mode == "custom" and len(categories) < 2:
        raise HTTPException(400, "Enter at least 2 categories")
    try:
        return jobs.start(
            "organize",
            lambda p: organizer.organize(p, req.mode, req.count, categories, req.strictness),
        )
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.get("/api/jobs/current")
def current_job():
    return jobs.current()


# ---------------------------------------------------------------- albums

class AlbumName(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ImageIds(BaseModel):
    image_ids: list[int]


@app.get("/api/albums")
def list_albums():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.name, a.kind, COUNT(ai.image_id) AS count,
                   (SELECT image_id FROM album_images WHERE album_id = a.id
                    ORDER BY score DESC LIMIT 1) AS cover_id
            FROM albums a LEFT JOIN album_images ai ON ai.album_id = a.id
            GROUP BY a.id ORDER BY count DESC, a.name
            """
        ).fetchall()
        unsorted = conn.execute(
            "SELECT COUNT(*) FROM images i LEFT JOIN album_images ai ON ai.image_id = i.id WHERE ai.image_id IS NULL"
        ).fetchone()[0]
    return {"albums": [dict(r) for r in rows], "unsorted": unsorted}


@app.post("/api/albums")
def create_album(req: AlbumName):
    with connect() as conn:
        album_id = conn.execute("INSERT INTO albums (name, kind) VALUES (?, 'manual')", (req.name.strip(),)).lastrowid
    return {"id": album_id, "name": req.name.strip()}


@app.patch("/api/albums/{album_id}")
def rename_album(album_id: int, req: AlbumName):
    with connect() as conn:
        conn.execute("UPDATE albums SET name = ? WHERE id = ?", (req.name.strip(), album_id))
    return {"id": album_id, "name": req.name.strip()}


@app.delete("/api/albums/{album_id}")
def delete_album(album_id: int):
    """Deletes the album; its photos become Unsorted. No files are touched."""
    with connect() as conn:
        conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))
    return {"deleted": album_id}


@app.post("/api/albums/{album_id}/images")
def move_to_album(album_id: int, req: ImageIds):
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM albums WHERE id = ?", (album_id,)).fetchone():
            raise HTTPException(404, "Album not found")
        conn.executemany(
            """
            INSERT INTO album_images (image_id, album_id, score, source) VALUES (?, ?, NULL, 'user')
            ON CONFLICT(image_id) DO UPDATE SET album_id = excluded.album_id, score = NULL, source = 'user'
            """,
            [(i, album_id) for i in req.image_ids],
        )
    return {"moved": len(req.image_ids)}


@app.post("/api/albums/unassign")
def unassign(req: ImageIds):
    with connect() as conn:
        conn.executemany("DELETE FROM album_images WHERE image_id = ?", [(i,) for i in req.image_ids])
    return {"unassigned": len(req.image_ids)}


# ---------------------------------------------------------------- export

class ExportRequest(BaseModel):
    dest: str
    include_unsorted: bool = False


@app.post("/api/export/preview")
def export_preview(req: ExportRequest):
    try:
        p = exporter.plan(req.dest, req.include_unsorted)
    except ValueError as e:
        raise HTTPException(400, str(e))
    p["sample"] = p.pop("items")[:8]
    return p


@app.post("/api/export/apply")
def export_apply(req: ExportRequest):
    try:
        return exporter.apply(req.dest, req.include_unsorted)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/export/{export_id}/undo")
def export_undo(export_id: int):
    try:
        return exporter.undo(export_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
