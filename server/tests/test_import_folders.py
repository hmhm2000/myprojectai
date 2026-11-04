"""Import folders: tiles read from the disk, remembered choice, files checked by their content."""
import os
import shutil
import zipfile
from pathlib import Path

from database.db import SessionLocal
from models.user import User
from services.imports.importer import import_entries, startup_import
from tests.conftest import login
from tests.test_bybit_import import JAN_MAR, write
from tests.test_okx_import import full_name, write as write_okx


def _folder():
    from config import settings
    folder = Path(settings.import_dir)
    shutil.rmtree(folder, ignore_errors=True)
    (folder / "okx").mkdir(parents=True)
    (folder / "bybitEU").mkdir()
    return folder


def _tiles(status):
    return {f["name"]: f for f in status["folders"]}


def test_tiles_come_from_the_folders_on_disk(client):
    headers = login(client)
    folder = _folder()
    (folder / "kraken").mkdir()
    (folder / "loose.csv").write_text("a,b\n1,2\n")
    write_okx(folder / "okx", full_name(), range(1, 4))
    try:
        tiles = _tiles(client.get("/api/import", headers=headers).json())
        assert set(tiles) == {"", "bybitEU", "kraken", "okx"}
        assert tiles["okx"]["portfolio"] == "OKX" and tiles["okx"]["files"] == 1 and tiles["okx"]["new"] == 1
        assert tiles["kraken"]["portfolio"] is None and tiles["kraken"]["selected"] is True
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_unticked_folder_is_skipped_and_the_choice_is_remembered(client):
    headers = login(client)
    folder = _folder()
    write_okx(folder / "okx", full_name(), range(1, 4))
    write(folder / "bybitEU", JAN_MAR, range(1, 4))
    try:
        status = client.put("/api/import/folders", json={"folder": "okx", "selected": False}, headers=headers).json()
        assert _tiles(status)["okx"]["selected"] is False
        status = client.post("/api/import/sync", headers=headers).json()
        assert [r["filename"] for r in status["last_sync"]] == [JAN_MAR]
        assert [p["name"] for p in status["portfolios"]] == ["Bybit.eu"]
        assert {f["folder"]: f["status"] for f in status["files"]} == {"okx": "skipped", "bybitEU": "imported"}

        again = client.post("/api/import/reprocess", headers=headers).json()       # remembered, reprocess too
        assert [r["filename"] for r in again["last_sync"]] == [JAN_MAR]
        startup_import()                                                           # the import at start-up too
        assert [p["name"] for p in client.get("/api/import", headers=headers).json()["portfolios"]] == ["Bybit.eu"]

        status = client.put("/api/import/folders", json={"folder": "okx", "selected": True}, headers=headers).json()
        assert _tiles(status)["okx"]["selected"] is True and _tiles(status)["okx"]["new"] == 1
        with SessionLocal() as db:
            assert db.query(User).first().import_skipped_folders == "[]"
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_every_file_is_checked_by_its_content(client):
    headers = login(client)
    folder = _folder()
    write_okx(folder / "okx", full_name(), range(1, 4))
    (folder / "okx" / full_name()).rename(folder / "okx" / "export.txt")          # the name doesn't matter
    (folder / "okx" / "statement.pdf").write_bytes(b"%PDF-1.7\n\x00\xff binary")
    (folder / "okx" / "trades.xlsx").write_bytes(b"PK\x03\x04 not really")
    (folder / "okx" / "broken.zip").write_bytes(b"not a zip")
    (folder / "okx" / "~$trades.xlsx").write_bytes(b"lock")
    (folder / "okx" / "desktop.ini").write_text("x")
    with zipfile.ZipFile(folder / "okx" / "mixed.zip", "w") as archive:
        archive.writestr("inner/", "")
        archive.writestr("inner/notes.pdf", b"%PDF-1.7")
    zipfile.ZipFile(folder / "okx" / "empty.zip", "w").close()
    try:
        status = client.post("/api/import/sync", headers=headers).json()
        assert {f["filename"]: f["status"] for f in status["files"]} == {
            "okx/export.txt": "imported", "okx/statement.pdf": "unrecognized", "okx/trades.xlsx": "unrecognized"}
        results = {r["filename"]: r["status"] for r in status["last_sync"]}
        assert results["export.txt"] == "imported" and results["notes.pdf"] == "unrecognized"
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_only_the_chosen_files_are_imported_and_the_newest_is_on_top(client):
    headers = login(client)
    folder = _folder()
    older = write_okx(folder / "okx", full_name(), range(1, 4))
    newer = write(folder / "bybitEU", JAN_MAR, range(1, 4))
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_800_000_000, 1_800_000_000))
    try:
        status = client.get("/api/import", headers=headers).json()
        assert [f["filename"] for f in status["files"]] == [f"bybitEU/{JAN_MAR}", f"okx/{full_name()}"]
        status = client.post("/api/import/sync", json={"files": [f"bybitEU/{JAN_MAR}"]}, headers=headers).json()
        assert [r["filename"] for r in status["last_sync"]] == [JAN_MAR]
        assert [f["status"] for f in status["files"]] == ["imported", "new"]
        status = client.post("/api/import/sync", json={"files": []}, headers=headers).json()
        assert status["last_sync"] == [] and status["files"][1]["status"] == "new"
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_a_file_that_cannot_be_read_does_not_stop_the_others(client, monkeypatch):
    headers = login(client)
    folder = _folder()
    write_okx(folder / "okx", full_name(), range(1, 4))
    write(folder / "bybitEU", JAN_MAR, range(1, 4))
    entry_type = type(import_entries(folder)[0])
    read = entry_type.read_bytes

    def locked(self):
        if self.path.parent.name == "okx":
            raise PermissionError("file is open in another program")
        return read(self)

    monkeypatch.setattr(entry_type, "read_bytes", locked)
    try:
        status = client.post("/api/import/sync", headers=headers).json()
        assert {r["filename"]: r["status"] for r in status["last_sync"]} == {full_name(): "error", JAN_MAR: "imported"}
        assert {f["folder"]: f["status"] for f in status["files"]} == {"okx": "error", "bybitEU": "imported"}
    finally:
        shutil.rmtree(folder, ignore_errors=True)
