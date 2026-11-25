"""Cleanup: find duplicates, blurry and dark photos, and (only when you confirm) send them to the Recycle Bin.

Nothing here deletes permanently. Rejected photos go to the Windows Recycle Bin, where they can be restored.
"""

import hashlib
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import ai
from .db import connect

# Two photos are near-duplicates if their difference hashes are this close (out of 64 bits)…
DHASH_SAME = 5
# …or if the hashes are fairly close AND the AI thinks the content is nearly identical (burst shots).
DHASH_LOOSE = 12
CLIP_SAME = 0.95

DEFAULT_BLUR_THRESHOLD = 60.0
DEFAULT_DARK_THRESHOLD = 35.0

IMAGE_COLUMNS = "i.id, i.folder_id, i.path, i.size, i.width, i.height, i.taken_at, q.sharpness, q.brightness"


def _items(rows) -> list[dict]:
    return [{**dict(r), "name": Path(r["path"]).name} for r in rows]


def _file_hash(path: str) -> str | None:
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


class _UnionFind:
    """Groups items that are linked by pairs (if A~B and B~C then A, B, C are one group)."""

    def __init__(self):
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int):
        self.parent[self.find(a)] = self.find(b)

    def groups(self) -> list[list[int]]:
        out = defaultdict(list)
        for x in self.parent:
            out[self.find(x)].append(x)
        return [g for g in out.values() if len(g) > 1]


def _candidates() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT {IMAGE_COLUMNS}, q.dhash, e.vector
            FROM images i
            LEFT JOIN image_quality q ON q.image_id = i.id
            LEFT JOIN embeddings e ON e.image_id = i.id AND e.model = ?
            WHERE COALESCE(q.ignored, 0) = 0
            """,
            (ai.MODEL_ID,),
        ).fetchall()
    return [dict(r) for r in rows]


def find_duplicates() -> dict:
    images = _candidates()
    by_id = {img["id"]: img for img in images}
    uf = _UnionFind()
    exact_pairs: set[tuple[int, int]] = set()

    # 1) Exact copies: same size AND same file contents. Only files sharing a size get hashed.
    by_size = defaultdict(list)
    for img in images:
        by_size[img["size"]].append(img)
    for same_size in by_size.values():
        if len(same_size) < 2:
            continue
        by_hash = defaultdict(list)
        for img in same_size:
            if (h := _file_hash(img["path"])) is not None:
                by_hash[h].append(img["id"])
        for ids in by_hash.values():
            for other in ids[1:]:
                uf.union(ids[0], other)
                exact_pairs.add((min(ids[0], other), max(ids[0], other)))

    # 2) Near-duplicates: compare perceptual hashes of every pair (vectorised, in chunks).
    hashed = [img for img in images if img["dhash"]]
    if len(hashed) > 1:
        values = np.array([int(img["dhash"], 16) for img in hashed], dtype=np.uint64)
        for start in range(0, len(hashed), 1000):
            block = values[start:start + 1000, None] ^ values[None, :]
            dist = np.bitwise_count(block)
            for a, b in zip(*np.nonzero(dist <= DHASH_LOOSE)):
                i, j = start + a, b
                if i >= j:
                    continue
                x, y = hashed[i], hashed[j]
                if dist[a, b] <= DHASH_SAME or _clip_similarity(x, y) >= CLIP_SAME:
                    uf.union(x["id"], y["id"])

    groups = []
    for ids in uf.groups():
        members = [by_id[i] for i in ids]
        best = max(members, key=lambda m: ((m["width"] or 0) * (m["height"] or 0), m["sharpness"] or 0, m["size"]))
        all_exact = all((min(best["id"], m["id"]), max(best["id"], m["id"])) in exact_pairs for m in members if m is not best)
        members.sort(key=lambda m: m is not best)  # best first
        for m in members:
            m.pop("vector", None)
            m.pop("dhash", None)
            m["name"] = Path(m["path"]).name
        groups.append({
            "kind": "exact" if all_exact else "similar",
            "keep_id": best["id"],
            "images": members,
            "reclaimable": sum(m["size"] for m in members if m is not best),
        })

    groups.sort(key=lambda g: -g["reclaimable"])
    return {"groups": groups, "reclaimable": sum(g["reclaimable"] for g in groups)}


def _clip_similarity(a: dict, b: dict) -> float:
    if not a["vector"] or not b["vector"]:
        return 0.0
    return float(np.frombuffer(a["vector"], dtype=np.float32) @ np.frombuffer(b["vector"], dtype=np.float32))


def find_blurry(threshold: float = DEFAULT_BLUR_THRESHOLD) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT {IMAGE_COLUMNS} FROM images i JOIN image_quality q ON q.image_id = i.id
            WHERE q.ignored = 0 AND q.sharpness IS NOT NULL AND q.sharpness < ?
            ORDER BY q.sharpness
            """,
            (threshold,),
        ).fetchall()
    return _items(rows)


def find_dark(threshold: float = DEFAULT_DARK_THRESHOLD) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT {IMAGE_COLUMNS} FROM images i JOIN image_quality q ON q.image_id = i.id
            WHERE q.ignored = 0 AND q.brightness IS NOT NULL AND q.brightness < ?
            ORDER BY q.brightness
            """,
            (threshold,),
        ).fetchall()
    return _items(rows)


def ignore(image_ids: list[int]) -> int:
    """Mark photos as reviewed ("keep") so Cleanup stops suggesting them."""
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO image_quality (image_id, ignored) VALUES (?, 1)
            ON CONFLICT(image_id) DO UPDATE SET ignored = 1
            """,
            [(i,) for i in image_ids],
        )
    return len(image_ids)


def send_to_recycle_bin(path: str):
    from send2trash import send2trash  # imported here so tests can swap it out easily

    send2trash(path)


def trash(image_ids: list[int]) -> dict:
    """Move photos to the Recycle Bin (recoverable) and remove them from the library."""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT id, path, size FROM images WHERE id IN ({','.join('?' * len(image_ids))})", image_ids
        ).fetchall() if image_ids else []

    trashed, freed, failed = [], 0, []
    for r in rows:
        try:
            if Path(r["path"]).exists():
                send_to_recycle_bin(r["path"])
            trashed.append(r["id"])
            freed += r["size"]
        except Exception as e:
            failed.append({"path": r["path"], "error": str(e)})

    with connect() as conn:
        conn.executemany("DELETE FROM images WHERE id = ?", [(i,) for i in trashed])
    return {"trashed": len(trashed), "freed": freed, "failed": failed}
