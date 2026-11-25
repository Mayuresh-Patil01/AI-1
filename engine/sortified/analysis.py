"""The "Analyze library" pass: makes sure every photo has quality scores and an AI embedding.

Organizing, search and Cleanup all build on this. It's incremental: only photos that are new or
changed since the last run are processed.
"""

from . import ai, quality
from .db import connect
from .jobs import Progress

BATCH = 32

# A photo needs (re)measuring if it has no quality row, or one written by an older version that
# didn't store every metric yet. Add new columns here when a migration adds a metric.
NEEDS_MEASURING = "q.tiny IS NULL OR q.highlights IS NULL"


def status() -> dict:
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        embedded = conn.execute("SELECT COUNT(*) FROM embeddings WHERE model = ?", (ai.MODEL_ID,)).fetchone()[0]
        measured = conn.execute(f"SELECT COUNT(*) FROM image_quality q WHERE NOT ({NEEDS_MEASURING})").fetchone()[0]
    return {"total": total, "embedded": embedded, "measured": measured, "pending": total - min(embedded, measured)}


def measure_missing(progress: Progress) -> int:
    with connect() as conn:
        todo = conn.execute(
            f"SELECT i.id, i.path FROM images i LEFT JOIN image_quality q ON q.image_id = i.id WHERE {NEEDS_MEASURING}"
        ).fetchall()
    if not todo:
        return 0

    progress.phase("Checking photo quality", total=len(todo))
    # Unreadable files get empty (not NULL) values so they aren't retried on every run.
    unreadable = {"sharpness": None, "brightness": None, "highlights": -1.0, "dhash": None, "tiny": b""}
    for start in range(0, len(todo), BATCH):
        rows = []
        for r in todo[start:start + BATCH]:
            m = quality.measure(r["path"]) or unreadable
            rows.append((r["id"], m["sharpness"], m["brightness"], m["highlights"], m["dhash"], m["tiny"]))
        with connect() as conn:
            # Upsert that keeps the "ignored" flag you may have set earlier.
            conn.executemany(
                """
                INSERT INTO image_quality (image_id, sharpness, brightness, highlights, dhash, tiny)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(image_id) DO UPDATE SET sharpness = excluded.sharpness, brightness = excluded.brightness,
                    highlights = excluded.highlights, dhash = excluded.dhash, tiny = excluded.tiny
                """,
                rows,
            )
        progress.step(len(rows))
    return len(todo)


def embed_missing(progress: Progress) -> int:
    with connect() as conn:
        todo = conn.execute(
            """
            SELECT i.id, i.path FROM images i
            LEFT JOIN embeddings e ON e.image_id = i.id AND e.model = ?
            WHERE e.image_id IS NULL
            """,
            (ai.MODEL_ID,),
        ).fetchall()
    if not todo:
        return 0

    if not ai.status()["loaded"]:
        progress.phase("Loading AI model (first run downloads ~600 MB)…")
        ai.embed_labels(["warm up"])  # triggers the load

    progress.phase(f"Analyzing photos with AI ({ai.status()['device'].upper()})", total=len(todo))
    for start in range(0, len(todo), BATCH):
        chunk = todo[start:start + BATCH]
        vectors = ai.embed_images([r["path"] for r in chunk])
        with connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO embeddings (image_id, model, vector) VALUES (?, ?, ?)",
                [(r["id"], ai.MODEL_ID, v.tobytes()) for r, v in zip(chunk, vectors) if v is not None],
            )
        progress.step(len(chunk))
    return len(todo)


def analyze(progress: Progress) -> dict:
    measured = measure_missing(progress)
    embedded = embed_missing(progress)
    # *_now = processed in this run; the rest (from status) are library totals.
    return {**status(), "measured_now": measured, "embedded_now": embedded}
