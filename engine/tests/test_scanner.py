import os

from PIL import Image

from sortified.db import connect
from sortified.scanner import scan_folder


def add_folder(path) -> int:
    with connect() as conn:
        return conn.execute("INSERT INTO folders (path) VALUES (?)", (str(path),)).lastrowid


def test_finds_images_in_subfolders_and_skips_other_files(photos):
    result = scan_folder(add_folder(photos), str(photos))
    assert result == {"added": 6, "updated": 0, "unchanged": 0, "removed": 0}


def test_rescan_only_processes_changes(photos):
    folder_id = add_folder(photos)
    scan_folder(folder_id, str(photos))

    assert scan_folder(folder_id, str(photos))["unchanged"] == 6

    # Change one photo, delete another, add a new one.
    changed = photos / "red_0.jpg"
    Image.new("RGB", (80, 80), (0, 0, 0)).save(changed)
    os.utime(changed, (1, 1))  # make sure mtime differs even on fast filesystems
    (photos / "red_1.jpg").unlink()
    Image.new("RGB", (10, 10)).save(photos / "new.webp")

    assert scan_folder(folder_id, str(photos)) == {"added": 1, "updated": 1, "unchanged": 4, "removed": 1}


def test_changed_photo_loses_its_stale_embedding(photos):
    folder_id = add_folder(photos)
    scan_folder(folder_id, str(photos))
    target = photos / "red_0.jpg"
    with connect() as conn:
        image_id = conn.execute("SELECT id FROM images WHERE path = ?", (str(target),)).fetchone()["id"]
        conn.execute("INSERT INTO embeddings (image_id, model, vector) VALUES (?, 'm', x'00')", (image_id,))

    os.utime(target, (1, 1))
    scan_folder(folder_id, str(photos))

    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0


def test_reads_exif_date(tmp_path):
    folder = tmp_path / "exif"
    folder.mkdir()
    img = Image.new("RGB", (8, 8))
    exif = img.getexif()
    exif.get_ifd(0x8769)[36867] = "2025:12:24 18:30:05"
    img.save(folder / "dated.jpg", exif=exif)

    scan_folder(add_folder(folder), str(folder))

    with connect() as conn:
        assert conn.execute("SELECT taken_at FROM images").fetchone()["taken_at"] == "2025-12-24T18:30:05"
