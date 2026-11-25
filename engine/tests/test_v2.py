"""v2 features: analysis, duplicates, blurry/dark photos, Recycle Bin, search, export templates."""

import shutil

import numpy as np
import pytest
from PIL import Image, ImageFilter

from conftest import wait_for_job
from sortified import cleanup, quality


def add(client, path) -> int:
    res = client.post("/api/folders", json={"path": str(path)})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def analyze(client):
    assert client.post("/api/analysis").status_code == 200
    job = wait_for_job()
    assert job["state"] == "done", job["error"]
    return job["result"]


def noisy(size=(320, 240), seed=0) -> Image.Image:
    """A detailed, sharp image (random texture)."""
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8))


@pytest.fixture
def messy(tmp_path):
    """A folder with a sharp photo, its exact copy, a smaller resized copy, a blurry and a dark photo."""
    root = tmp_path / "messy"
    root.mkdir()
    noisy(seed=1).save(root / "original.png")
    shutil.copyfile(root / "original.png", root / "original_copy.png")
    noisy(seed=1).resize((160, 120)).save(root / "original_small.png")
    noisy(seed=2).filter(ImageFilter.GaussianBlur(8)).save(root / "blurry.png")
    Image.fromarray((np.asarray(noisy(seed=3)) * 0.06).astype(np.uint8)).save(root / "dark.png")
    noisy(seed=4).save(root / "unrelated.png")
    return root


# ---------------------------------------------------------------- quality metrics

def test_sharpness_and_brightness_tell_photos_apart():
    def gray(img):
        return np.asarray(img.convert("L"), dtype=np.float32)

    sharp, blurred, smaller = gray(noisy()), gray(noisy().filter(ImageFilter.GaussianBlur(8))), gray(noisy().resize((160, 120)))
    assert quality.sharpness(sharp) > 10 * quality.sharpness(blurred)
    assert quality.hamming(quality.dhash(sharp), quality.dhash(smaller)) <= quality_threshold()
    assert quality.hamming(quality.dhash(sharp), quality.dhash(gray(noisy(seed=99)))) > 20  # unrelated photo


def quality_threshold() -> int:
    return cleanup.DHASH_SAME


def test_analysis_is_incremental(client, messy, fake_ai):
    add(client, messy)
    first = analyze(client)
    assert first["measured_now"] == 6 and first["embedded_now"] == 6 and first["pending"] == 0
    second = analyze(client)
    assert second["measured_now"] == 0 and second["embedded_now"] == 0
    assert second["measured"] == 6 and second["total"] == 6


# ---------------------------------------------------------------- cleanup

def test_finds_exact_and_resized_duplicates_and_keeps_the_biggest(client, messy, fake_ai):
    add(client, messy)
    analyze(client)

    groups = client.get("/api/cleanup/duplicates").json()["groups"]
    assert len(groups) == 1
    names = {img["name"] for img in groups[0]["images"]}
    assert names == {"original.png", "original_copy.png", "original_small.png"}
    assert groups[0]["kind"] == "similar"  # the resized one isn't byte-identical
    keep = next(i for i in groups[0]["images"] if i["id"] == groups[0]["keep_id"])
    assert keep["name"] in {"original.png", "original_copy.png"}  # full resolution wins over the small copy


def test_exact_copies_only(client, tmp_path, fake_ai):
    root = tmp_path / "exact"
    root.mkdir()
    noisy(seed=9).save(root / "a.png")
    shutil.copyfile(root / "a.png", root / "b.png")
    add(client, root)
    analyze(client)
    groups = client.get("/api/cleanup/duplicates").json()["groups"]
    assert len(groups) == 1 and groups[0]["kind"] == "exact"


def test_blurry_and_dark(client, messy, fake_ai):
    add(client, messy)
    analyze(client)
    assert [i["name"] for i in client.get("/api/cleanup/blurry").json()["items"]] == ["blurry.png"]
    assert [i["name"] for i in client.get("/api/cleanup/dark").json()["items"]] == ["dark.png"]


def test_keep_hides_photo_from_cleanup(client, messy, fake_ai):
    add(client, messy)
    analyze(client)
    blurry = client.get("/api/cleanup/blurry").json()["items"][0]
    client.post("/api/cleanup/keep", json={"image_ids": [blurry["id"]]})
    assert client.get("/api/cleanup/blurry").json()["items"] == []


def test_trash_moves_files_to_recycle_bin_and_out_of_library(client, messy, fake_ai, tmp_path, monkeypatch):
    bin_dir = tmp_path / "RecycleBin"
    bin_dir.mkdir()
    monkeypatch.setattr(cleanup, "send_to_recycle_bin", lambda p: shutil.move(p, bin_dir))
    add(client, messy)
    analyze(client)

    group = client.get("/api/cleanup/duplicates").json()["groups"][0]
    rejects = [i["id"] for i in group["images"] if i["id"] != group["keep_id"]]
    result = client.post("/api/cleanup/trash", json={"image_ids": rejects}).json()

    assert result["trashed"] == 2 and result["failed"] == []
    assert result["freed"] == group["reclaimable"]
    assert len(list(bin_dir.iterdir())) == 2
    assert client.get("/api/images").json()["total"] == 4
    assert client.get("/api/cleanup/duplicates").json()["groups"] == []


# ---------------------------------------------------------------- search

def test_search_finds_matching_photos(client, photos, fake_ai):
    add(client, photos)
    analyze(client)
    res = client.get("/api/search", params={"q": "red"}).json()
    assert {i["name"].split("_")[0] for i in res["items"]} == {"red"}
    assert len(res["items"]) == 3
    assert res["items"][0]["score"] >= res["items"][-1]["score"]


def test_search_with_nothing_relevant_returns_nothing(client, photos, fake_ai):
    add(client, photos)
    analyze(client)
    assert client.get("/api/search", params={"q": "green"}).json()["items"] == []


# ---------------------------------------------------------------- export templates

@pytest.fixture
def dated_photos(tmp_path):
    root = tmp_path / "dated"
    root.mkdir()
    for i, date in enumerate(["2024:07:04 10:00:00", "2025:12:24 18:30:05"]):
        img = Image.new("RGB", (32, 32), (220, 30, 30))
        exif = img.getexif()
        exif.get_ifd(0x8769)[36867] = date
        img.save(root / f"red_{i}.jpg", exif=exif)
    return root


def test_export_with_year_template_and_full_undo(client, dated_photos, fake_ai, tmp_path):
    add(client, dated_photos)
    client.post("/api/organize", json={"mode": "custom", "categories": ["Red", "Blue"]})
    wait_for_job()
    dest = tmp_path / "Out"
    body = {"dest": str(dest), "template": "{year}/{month_name} - {album}"}

    preview = client.post("/api/export/preview", json=body).json()
    assert {f["name"] for f in preview["folders"]} == {"2024\\July - Red", "2025\\December - Red"}

    result = client.post("/api/export/apply", json=body).json()
    assert (dest / "2024" / "July - Red" / "red_0.jpg").exists()
    assert (dest / "2025" / "December - Red" / "red_1.jpg").exists()

    client.post(f"/api/export/{result['id']}/undo")
    assert list(dest.iterdir()) == [], "undo should also remove the empty year folders it created"


@pytest.mark.parametrize("template", ["{albm}", "no fields here"])
def test_bad_template_is_rejected(client, photos, fake_ai, tmp_path, template):
    add(client, photos)
    res = client.post("/api/export/preview", json={"dest": str(tmp_path / "o"), "template": template})
    assert res.status_code == 400
