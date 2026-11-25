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
