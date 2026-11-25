"""Builds albums from the AI embeddings.

Two modes:
  * auto   — group similar photos (k-means clustering), then name each group with the best label.
  * custom — you give category names; each photo goes to the category its content matches best.
"""

import numpy as np

from . import ai
from .db import connect
from .jobs import Progress
from .labels import ALBUM_LABELS

BATCH = 32


# ---------- step 1: make sure every image has an embedding ----------

def index_missing(progress: Progress) -> int:
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

    progress.phase(f"Analyzing photos on {ai.status()['device'].upper()}", total=len(todo))
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


def load_embeddings() -> tuple[list[int], np.ndarray]:
    with connect() as conn:
        rows = conn.execute("SELECT image_id, vector FROM embeddings WHERE model = ?", (ai.MODEL_ID,)).fetchall()
    ids = [r["image_id"] for r in rows]
    if not rows:
        return ids, np.zeros((0, 0), dtype=np.float32)
    return ids, np.stack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])


# ---------- step 2: build albums ----------

def _normalize(m: np.ndarray) -> np.ndarray:
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


def auto_albums(ids: list[int], vecs: np.ndarray, count: int | None) -> dict[str, list[tuple[int, float]]]:
    n = len(ids)
    if n < 4:
        return {"Photos": [(i, 1.0) for i in ids]}

    k = count or int(np.clip(round(np.sqrt(n / 2)), 2, 24))
    k = min(k, n)
    from sklearn.cluster import KMeans, MiniBatchKMeans

    km = (MiniBatchKMeans if n > 5000 else KMeans)(n_clusters=k, n_init="auto", random_state=0)
    assignment = km.fit_predict(vecs)
    centroids = _normalize(km.cluster_centers_.astype(np.float32))

    # Name each cluster by the label closest to its centre.
    label_vecs = ai.embed_labels(ALBUM_LABELS)
    names = [ALBUM_LABELS[j] for j in (centroids @ label_vecs.T).argmax(axis=1)]

    # Clusters that got the same name are the same theme -> merge them.
    albums: dict[str, list[tuple[int, float]]] = {}
    for idx, (image_id, cluster) in enumerate(zip(ids, assignment)):
        score = float(vecs[idx] @ centroids[cluster])
        albums.setdefault(names[cluster], []).append((image_id, score))
    return albums


def custom_albums(ids: list[int], vecs: np.ndarray, categories: list[str], strictness: float):
    """strictness 0..1: higher = only confident matches, the rest stay Unsorted."""
    label_vecs = ai.embed_labels(categories)
    sims = vecs @ label_vecs.T                      # cosine similarity, shape (images, categories)
    probs = ai.softmax(sims * ai.LOGIT_SCALE)       # how much each photo "prefers" each category
    best = probs.argmax(axis=1)

    min_prob = 0.3 + 0.6 * strictness               # 0.30 .. 0.90
    min_sim = 0.15 + 0.07 * strictness              # absolute floor so random photos aren't forced in
    albums: dict[str, list[tuple[int, float]]] = {c: [] for c in categories}
    for idx, image_id in enumerate(ids):
        c = best[idx]
        if probs[idx, c] >= min_prob and sims[idx, c] >= min_sim:
            albums[categories[c]].append((image_id, float(probs[idx, c])))
    return albums


def save_albums(albums: dict[str, list[tuple[int, float]]], kind: str) -> list[dict]:
    """Replace ALL existing albums with these ones."""
    with connect() as conn:
        conn.execute("DELETE FROM albums")
        out = []
        for name, members in sorted(albums.items(), key=lambda kv: -len(kv[1])):
            album_id = conn.execute("INSERT INTO albums (name, kind) VALUES (?, ?)", (name, kind)).lastrowid
            conn.executemany(
                "INSERT INTO album_images (image_id, album_id, score, source) VALUES (?, ?, ?, 'ai')",
                [(image_id, album_id, score) for image_id, score in members],
            )
            out.append({"id": album_id, "name": name, "count": len(members)})
    return out


def organize(progress: Progress, mode: str, count: int | None, categories: list[str], strictness: float) -> dict:
    analyzed = index_missing(progress)

    progress.phase("Building albums…")
    ids, vecs = load_embeddings()
    if not ids:
        raise RuntimeError("No photos to organize. Add a folder first.")

    if mode == "custom":
        albums = custom_albums(ids, vecs, categories, strictness)
    else:
        albums = auto_albums(ids, vecs, count)

    saved = save_albums(albums, kind=mode)
    placed = sum(a["count"] for a in saved)
    return {"analyzed": analyzed, "albums": saved, "placed": placed, "unsorted": len(ids) - placed}
