"""SQLite database: remembers which folders, images and albums are in the library.

Schema changes are done with MIGRATIONS (see the bottom of this file), so a library created by an
older version of SORTIFIED is upgraded automatically and nobody loses their albums.
"""

import shutil
import sqlite3
from contextlib import contextmanager

from . import config


@contextmanager
def connect():
    """Open the database, commit on success, always close.

    Usage:
        with connect() as conn:
            conn.execute(...)
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["path"]
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------------------------
# MIGRATIONS
#
# Each entry upgrades the database by one version. The database remembers its version in
# SQLite's built-in `PRAGMA user_version`.
#
# HOW TO CHANGE THE SCHEMA:
#   * NEVER edit a migration that has already been committed — other PCs have already run it.
#   * Instead, APPEND a new SQL string to the list, e.g.:
#         "ALTER TABLE images ADD COLUMN blur_score REAL;",
#   * Add a test for it in engine/tests/test_db.py.
# ---------------------------------------------------------------------------------------------

MIGRATIONS: list[str] = [
    # 1 — v0.1 + v1.0: folders, images, embeddings, albums, exports
    """
    CREATE TABLE IF NOT EXISTS folders (
        id          INTEGER PRIMARY KEY,
        path        TEXT NOT NULL UNIQUE,
        added_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS images (
        id          INTEGER PRIMARY KEY,
        folder_id   INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
        path        TEXT NOT NULL UNIQUE,
        size        INTEGER NOT NULL,      -- bytes
        mtime       REAL NOT NULL,         -- last modified (used to skip unchanged files)
        width       INTEGER,
        height      INTEGER,
        taken_at    TEXT                   -- from EXIF, if the photo has it
    );
    CREATE INDEX IF NOT EXISTS idx_images_folder ON images(folder_id);

    -- AI "fingerprint" of each image (CLIP embedding), stored as raw float32 bytes.
    CREATE TABLE IF NOT EXISTS embeddings (
        image_id    INTEGER PRIMARY KEY REFERENCES images(id) ON DELETE CASCADE,
        model       TEXT NOT NULL,
        vector      BLOB NOT NULL
    );

    CREATE TABLE IF NOT EXISTS albums (
        id          INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        kind        TEXT NOT NULL,          -- 'auto' (discovered), 'custom' (your category), 'manual'
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Which album each image is in. An image is in at most one album.
    CREATE TABLE IF NOT EXISTS album_images (
        image_id    INTEGER PRIMARY KEY REFERENCES images(id) ON DELETE CASCADE,
        album_id    INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
        score       REAL,                   -- how confident the AI was (NULL if you placed it)
        source      TEXT NOT NULL           -- 'ai' or 'user'
    );
    CREATE INDEX IF NOT EXISTS idx_album_images_album ON album_images(album_id);

    -- Every export is logged so it can be undone.
    CREATE TABLE IF NOT EXISTS exports (
        id          INTEGER PRIMARY KEY,
        dest        TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        files       TEXT NOT NULL,          -- JSON list of {"dst": ..., "size": ...} we created
        undone      INTEGER NOT NULL DEFAULT 0
    );
    """,
    # 2 — v2.0: photo quality metrics for the Cleanup view
    """
    CREATE TABLE image_quality (
        image_id    INTEGER PRIMARY KEY REFERENCES images(id) ON DELETE CASCADE,
        sharpness   REAL,                   -- higher = sharper (variance of edges)
        brightness  REAL,                   -- average brightness 0..255
        dhash       TEXT,                   -- 64-bit "difference hash" as 16 hex chars, for near-duplicates
        ignored     INTEGER NOT NULL DEFAULT 0  -- 1 = you marked it "keep" in Cleanup
    );
    """,
]

def schema_version() -> int:
    """The newest schema version this code knows about."""
    return len(MIGRATIONS)


def get_version() -> int:
    """The schema version the database on disk is at."""
    with connect() as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def init_db():
    """Create the database, or upgrade an older one to the latest schema."""
    current = get_version() if config.DB_PATH.exists() else 0
    latest = schema_version()
    if current > latest:
        raise RuntimeError(
            f"This library was made by a newer SORTIFIED (schema v{current}, this app knows v{latest}). "
            "Run `git pull` to update the app."
        )
    if current == latest:
        return

    # Safety net: keep a copy of the old library before changing its structure.
    if current > 0:
        shutil.copy2(config.DB_PATH, config.DB_PATH.with_suffix(f".v{current}.bak"))

    for version in range(current + 1, latest + 1):
        with connect() as conn:
            conn.executescript(MIGRATIONS[version - 1])
            conn.execute(f"PRAGMA user_version = {version}")
