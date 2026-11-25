import sqlite3

import pytest

from sortified import config, db


def test_fresh_database_is_at_latest_version():
    assert db.get_version() == db.schema_version()


def test_init_is_idempotent():
    db.init_db()
    db.init_db()
    assert db.get_version() == db.schema_version()


def test_library_from_before_migrations_is_upgraded_and_keeps_data(tmp_path, monkeypatch):
    # A v1.0 library had the tables but no version number (user_version = 0).
    old = tmp_path / "old.db"
    conn = sqlite3.connect(old)
    conn.executescript(db.MIGRATIONS[0])
    conn.execute("INSERT INTO folders (path) VALUES ('C:/photos')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "DB_PATH", old)
    db.init_db()

    assert db.get_version() == db.schema_version()
    with db.connect() as c:
        assert c.execute("SELECT path FROM folders").fetchone()["path"] == "C:/photos"


def test_new_migration_runs_and_backs_up_old_library(monkeypatch):
    monkeypatch.setattr(db, "MIGRATIONS", [*db.MIGRATIONS, "ALTER TABLE images ADD COLUMN blur_score REAL;"])
    before = db.get_version()

    db.init_db()

    assert db.get_version() == before + 1
    with db.connect() as c:
        columns = [r["name"] for r in c.execute("PRAGMA table_info(images)")]
    assert "blur_score" in columns
    assert config.DB_PATH.with_suffix(f".v{before}.bak").exists()


def test_library_from_newer_app_is_refused():
    with db.connect() as c:
        c.execute(f"PRAGMA user_version = {db.schema_version() + 1}")
    with pytest.raises(RuntimeError, match="newer SORTIFIED"):
        db.init_db()
