"""SQLite database: remembers which folders and images are in the library."""

import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
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
"""


@contextmanager
def connect():
    """Open the database, commit on success, always close.

    Usage:
        with connect() as conn:
            conn.execute(...)
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["path"]
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
