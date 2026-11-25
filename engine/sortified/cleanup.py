"""Cleanup: find duplicates, blurry and dark photos, and (only when you confirm) send them to the Recycle Bin.

Nothing here deletes permanently. Rejected photos go to the Windows Recycle Bin, where they can be restored.
"""

import hashlib
from collections import defaultdict
from pathlib import Path

import numpy as np

from .db import connect

# Near-duplicates are found in two steps:
#  1. fast filter: difference hashes within DHASH_LOOSE bits (out of 64) -> "might be the same photo"
#  2. confirm: the 32x32 versions correlate at least TINY_SAME -> "really is the same photo"
# Step 2 matters: screenshots or documents with the same layout often share a dHash but aren't duplicates.
DHASH_SAME = 5          # used by tests as "clearly the same hash"
DHASH_LOOSE = 12
TINY_SAME = 0.96        # real copies score ~0.99; different screenshots sharing a layout reach ~0.91

DEFAULT_BLUR_THRESHOLD = 60.0
DEFAULT_DARK_THRESHOLD = 25.0
# "Too dark" means dark everywhere (pocket shots, lens cap). Dark-mode screenshots and night photos
# are dark on average but have bright text or lights, so their brightest 1% is well above this.
DARK_MAX_HIGHLIGHTS = 70.0

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
            SELECT {IMAGE_COLUMNS}, q.dhash, q.tiny
            FROM images i LEFT JOIN image_quality q ON q.image_id = i.id
            WHERE COALESCE(q.ignored, 0) = 0
            """
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

    # 2) Near-duplicates: dHash filter on every pair (vectorised, in chunks), then confirm with the tiny images.
    hashed = [img for img in images if img["dhash"] and img["tiny"]]
    if len(hashed) > 1:
        values = np.array([int(img["dhash"], 16) for img in hashed], dtype=np.uint64)
        tinies = np.stack([np.frombuffer(img["tiny"], dtype=np.float16).astype(np.float32) for img in hashed])
        for start in range(0, len(hashed), 1000):
            dist = np.bitwise_count(values[start:start + 1000, None] ^ values[None, :])
            rows, cols = np.nonzero(dist <= DHASH_LOOSE)
            rows = rows + start
            keep = rows < cols  # each pair once, skip self-pairs
            rows, cols = rows[keep], cols[keep]
            correlation = np.einsum("ij,ij->i", tinies[rows], tinies[cols])
            for i, j in zip(rows[correlation >= TINY_SAME], cols[correlation >= TINY_SAME]):
                uf.union(hashed[i]["id"], hashed[j]["id"])

    groups = []
    for ids in uf.groups():
        members = [by_id[i] for i in ids]
        best = max(members, key=lambda m: ((m["width"] or 0) * (m["height"] or 0), m["sharpness"] or 0, m["size"]))
        all_exact = all((min(best["id"], m["id"]), max(best["id"], m["id"])) in exact_pairs for m in members if m is not best)
        members.sort(key=lambda m: m is not best)  # best first
        for m in members:
            m.pop("tiny", None)
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


def find_blurry(threshold: float = DEFAULT_BLUR_THRESHOLD) -> list[dict]:
    # Very dark photos always have weak edges, so they'd look "blurry" too. They're listed under
    # "Too dark" instead, so leave them out here.
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT {IMAGE_COLUMNS} FROM images i JOIN image_quality q ON q.image_id = i.id
            WHERE q.ignored = 0 AND q.sharpness IS NOT NULL AND q.sharpness < ?
              AND COALESCE(q.brightness, 255) >= ?
            ORDER BY q.sharpness
            """,
            (threshold, DEFAULT_DARK_THRESHOLD),
        ).fetchall()
    return _items(rows)


def find_dark(threshold: float = DEFAULT_DARK_THRESHOLD) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT {IMAGE_COLUMNS} FROM images i JOIN image_quality q ON q.image_id = i.id
            WHERE q.ignored = 0 AND q.brightness IS NOT NULL AND q.brightness < ?
              AND COALESCE(q.highlights, 0) < ?
            ORDER BY q.brightness
            """,
            (threshold, DARK_MAX_HIGHLIGHTS),
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
