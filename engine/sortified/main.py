"""The local API the UI talks to. Run with:

    .venv\\Scripts\\python -m uvicorn sortified.main:app --reload --port 8000

Then open http://127.0.0.1:8000/docs to try every endpoint in the browser.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import __version__
from .db import connect, init_db
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


class AddFolderRequest(BaseModel):
    path: str


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


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


@app.get("/api/images")
def list_images(folder_id: int | None = None, offset: int = 0, limit: int = 200):
    where, params = ("WHERE folder_id = ?", [folder_id]) if folder_id else ("", [])
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM images {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, folder_id, path, size, width, height, taken_at FROM images {where}
            ORDER BY COALESCE(taken_at, '') DESC, path LIMIT ? OFFSET ?
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
    return FileResponse(thumb, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})
