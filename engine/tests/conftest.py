"""Shared test setup.

Tests never touch your real library (~/.sortified) and never download the AI model:
  * every test gets its own empty database in a temp folder
  * `fake_ai` swaps CLIP for a tiny stand-in that "sees" an image's main colour
"""

import os
import tempfile
import time

# Must happen before sortified is imported, so config points at a throwaway folder.
os.environ["SORTIFIED_DATA"] = tempfile.mkdtemp(prefix="sortified-test-")

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from sortified import ai, config, db, jobs, organizer


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "library.db")
    db.init_db()
    yield


@pytest.fixture
def client():
    from sortified.main import app

    return TestClient(app)


COLORS = {"red": (220, 30, 30), "blue": (30, 30, 220), "green": (30, 200, 30)}


@pytest.fixture
def photos(tmp_path):
    """A folder with 3 red + 3 blue photos (one in a subfolder), a text file and a broken image."""
    root = tmp_path / "photos"
    (root / "sub").mkdir(parents=True)
    for i in range(3):
        Image.new("RGB", (64, 48), COLORS["red"]).save(root / f"red_{i}.jpg")
        Image.new("RGB", (64, 48), COLORS["blue"]).save((root / "sub" if i == 0 else root) / f"blue_{i}.png")
    (root / "notes.txt").write_text("not an image")
    return root


def _color_vector(rgb) -> np.ndarray:
    # Centre on grey so different colours point in clearly different directions (like real CLIP vectors).
    v = np.array([*(np.asarray(rgb, dtype=np.float32) - 128), 1.0], dtype=np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture
def fake_ai(monkeypatch):
    """Replace CLIP with a stand-in: an image's vector is its average colour; labels map to colours."""

    def embed_images(paths):
        out = []
        for p in paths:
            try:
                with Image.open(p) as img:
                    out.append(_color_vector(np.asarray(img.convert("RGB")).reshape(-1, 3).mean(axis=0)))
            except Exception:
                out.append(None)
        return out

    def embed_labels(labels):
        return np.stack([_color_vector(COLORS.get(l.lower().split()[0], (128, 128, 128))) for l in labels])

    monkeypatch.setattr(ai, "embed_images", embed_images)
    monkeypatch.setattr(ai, "embed_labels", embed_labels)
    monkeypatch.setattr(ai, "status", lambda: {"model": ai.MODEL_ID, "loaded": True, "device": "cpu"})
    monkeypatch.setattr(organizer, "ALBUM_LABELS", ["Red Things", "Blue Things", "Green Things"])
    # The softmax scale is tuned for real CLIP similarities; the fake vectors need a sharper one.
    monkeypatch.setattr(ai, "LOGIT_SCALE", 500.0)


def wait_for_job(timeout: float = 10) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        job = jobs.current()
        if job and job["state"] != "running":
            return job
        time.sleep(0.05)
    raise TimeoutError("job did not finish")
