"""End-to-end tests through the HTTP API, the same way the UI uses it."""

from pathlib import Path

from conftest import wait_for_job


def add(client, path) -> int:
    res = client.post("/api/folders", json={"path": str(path)})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def names_in(client, album_id) -> set[str]:
    return {i["name"].split("_")[0] for i in client.get(f"/api/images?album_id={album_id}").json()["items"]}


def organize(client, **options) -> dict:
    res = client.post("/api/organize", json=options)
    assert res.status_code == 200, res.text
    job = wait_for_job()
    assert job["state"] == "done", job["error"]
    return job["result"]


# ---------------------------------------------------------------- folders & images

def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["schema"] >= 1


def test_add_folder_lists_images(client, photos):
    folder_id = add(client, photos)
    assert client.get("/api/folders").json()[0]["image_count"] == 6
    assert client.get(f"/api/images?folder_id={folder_id}").json()["total"] == 6


def test_add_missing_folder_is_rejected(client, tmp_path):
    assert client.post("/api/folders", json={"path": str(tmp_path / "nope")}).status_code == 400


def test_thumbnails(client, photos):
    add(client, photos)
    image = client.get("/api/images").json()["items"][0]
    for size in ("thumb", "large"):
        res = client.get(f"/api/images/{image['id']}/thumbnail?size={size}")
        assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
    assert client.get("/api/images/99999/thumbnail").status_code == 404


def test_removing_folder_keeps_files(client, photos):
    folder_id = add(client, photos)
    client.delete(f"/api/folders/{folder_id}")
    assert client.get("/api/folders").json() == []
    assert len(list(photos.rglob("*.*"))) == 7  # 6 images + notes.txt still on disk


# ---------------------------------------------------------------- AI organizing

def test_auto_albums_group_and_name_photos(client, photos, fake_ai):
    add(client, photos)
    result = organize(client, mode="auto", count=2)

    albums = {a["name"]: a["id"] for a in client.get("/api/albums").json()["albums"]}
    assert set(albums) == {"Red Things", "Blue Things"}
    assert names_in(client, albums["Red Things"]) == {"red"}
    assert names_in(client, albums["Blue Things"]) == {"blue"}
    assert result["placed"] == 6 and result["unsorted"] == 0


def test_custom_categories_leave_unmatched_photos_unsorted(client, photos, fake_ai):
    add(client, photos)
    result = organize(client, mode="custom", categories=["Red", "Green"], strictness=0.5)

    albums = {a["name"]: a for a in client.get("/api/albums").json()["albums"]}
    assert albums["Red"]["count"] == 3
    assert albums["Green"]["count"] == 0
    assert result["unsorted"] == 3  # the blue photos fit neither category


def test_custom_mode_needs_two_categories(client, photos, fake_ai):
    add(client, photos)
    assert client.post("/api/organize", json={"mode": "custom", "categories": ["Red"]}).status_code == 400


def test_move_rename_and_delete_albums(client, photos, fake_ai):
    add(client, photos)
    organize(client, mode="auto", count=2)
    albums = {a["name"]: a["id"] for a in client.get("/api/albums").json()["albums"]}
    red = client.get(f"/api/images?album_id={albums['Red Things']}").json()["items"][0]["id"]

    client.post(f"/api/albums/{albums['Blue Things']}/images", json={"image_ids": [red]})
    assert client.get(f"/api/images?album_id={albums['Blue Things']}").json()["total"] == 4

    client.post("/api/albums/unassign", json={"image_ids": [red]})
    assert client.get("/api/albums").json()["unsorted"] == 1

    client.patch(f"/api/albums/{albums['Blue Things']}", json={"name": "Ocean"})
    assert "Ocean" in [a["name"] for a in client.get("/api/albums").json()["albums"]]

    client.delete(f"/api/albums/{albums['Red Things']}")
    assert client.get("/api/albums").json()["unsorted"] == 3


# ---------------------------------------------------------------- export

def test_export_preview_copy_and_undo(client, photos, fake_ai, tmp_path):
    add(client, photos)
    organize(client, mode="custom", categories=["Red", "Green"], strictness=0.5)
    dest = tmp_path / "Sorted"
    originals = sorted(p.read_bytes() for p in photos.rglob("*.*"))

    preview = client.post("/api/export/preview", json={"dest": str(dest), "include_unsorted": True}).json()
    assert preview["total"] == 6
    assert {f["name"] for f in preview["folders"]} == {"Red", "Unsorted"}
    assert not dest.exists(), "preview must not touch the disk"

    result = client.post("/api/export/apply", json={"dest": str(dest), "include_unsorted": True}).json()
    assert result["copied"] == 6 and result["failed"] == []
    assert len(list((dest / "Red").iterdir())) == 3
    assert len(list((dest / "Unsorted").iterdir())) == 3

    undo = client.post(f"/api/export/{result['id']}/undo").json()
    assert undo == {"removed": 6, "kept": 0}
    assert not (dest / "Red").exists()
    assert client.post(f"/api/export/{result['id']}/undo").status_code == 400  # can't undo twice

    assert sorted(p.read_bytes() for p in photos.rglob("*.*")) == originals, "originals must never change"


def test_export_never_overwrites_existing_files(client, photos, fake_ai, tmp_path):
    add(client, photos)
    organize(client, mode="custom", categories=["Red", "Green"], strictness=0.5)
    dest = tmp_path / "Sorted"
    (dest / "Red").mkdir(parents=True)
    (dest / "Red" / "red_0.jpg").write_text("my own file")

    client.post("/api/export/apply", json={"dest": str(dest)})

    assert (dest / "Red" / "red_0.jpg").read_text() == "my own file"
    assert (dest / "Red" / "red_0_1.jpg").exists()


def test_export_inside_library_folder_is_refused(client, photos, fake_ai):
    add(client, photos)
    res = client.post("/api/export/preview", json={"dest": str(Path(photos) / "out")})
    assert res.status_code == 400 and "inside a library folder" in res.json()["detail"]
