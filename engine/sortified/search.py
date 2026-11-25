"""Search photos by describing them ("red car at night") using the CLIP embeddings."""

from pathlib import Path

import numpy as np

from . import ai
from .db import connect
from .organizer import load_embeddings

MIN_SCORE = 0.19      # below this, CLIP is basically saying "unrelated"
WINDOW = 0.10         # keep results within this distance of the best match


def search(query: str, limit: int = 100) -> dict:
    ids, vecs = load_embeddings()
    if not ids:
        return {"items": [], "searched": 0}

    text = ai.embed_labels([query])[0]
    scores = vecs @ text
    order = np.argsort(-scores)[:limit]
    cutoff = max(MIN_SCORE, float(scores[order[0]]) - WINDOW)
    keep = [(ids[i], float(scores[i])) for i in order if scores[i] >= cutoff]
    if not keep:
        return {"items": [], "searched": len(ids)}

    score_by_id = dict(keep)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT i.id, i.folder_id, i.path, i.size, i.width, i.height, i.taken_at, ai.album_id
            FROM images i LEFT JOIN album_images ai ON ai.image_id = i.id
            WHERE i.id IN ({','.join('?' * len(keep))})
            """,
            list(score_by_id),
        ).fetchall()
    items = [{**dict(r), "name": Path(r["path"]).name, "score": score_by_id[r["id"]]} for r in rows]
    items.sort(key=lambda x: -x["score"])
    return {"items": items, "searched": len(ids)}
