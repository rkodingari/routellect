from __future__ import annotations

import io
import json
import sqlite3
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from routellect.backup import create_backup, restore_backup
from routellect.storage import Store


def test_backup_restore_round_trip_and_refuse_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source"
    store = Store(source / "routellect.sqlite3")
    store.initialize()
    catalogs = source / "catalogs"
    catalogs.mkdir()
    (catalogs / "trusted-public-keys.json").write_text('{"qa":"public"}\n')

    archive = tmp_path / "routellect-backup.tar.gz"
    created = create_backup(source, archive)
    assert created["format"] == "routellect-backup-v1"
    assert len(created["archive_sha256"]) == 64

    restored = tmp_path / "restored"
    receipt = restore_backup(archive, restored)
    assert receipt["restored_files"] == 2
    assert (restored / "catalogs" / "trusted-public-keys.json").read_text() == (
        '{"qa":"public"}\n'
    )
    with sqlite3.connect(restored / "routellect.sqlite3") as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    with pytest.raises(FileExistsError):
        create_backup(source, archive)
    with pytest.raises(FileExistsError):
        restore_backup(archive, restored)


def test_restore_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        payload = b"unsafe"
        member = tarfile.TarInfo("../outside")
        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))
    with pytest.raises(ValueError, match="unsafe backup member"):
        restore_backup(archive, tmp_path / "target")


def test_restore_rejects_malformed_manifest_item(tmp_path: Path) -> None:
    archive = tmp_path / "malformed.tar.gz"
    manifest = json.dumps(
        {"format": "routellect-backup-v1", "created_at": "now", "files": [{}]}
    ).encode()
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo("manifest.json")
        member.size = len(manifest)
        tar.addfile(member, io.BytesIO(manifest))
    with pytest.raises(ValueError, match="manifest is invalid"):
        restore_backup(archive, tmp_path / "target")


def test_explicit_retention_purge(tmp_path: Path) -> None:
    database = tmp_path / "retention.sqlite3"
    store = Store(database)
    store.initialize()
    now = datetime(2026, 9, 16, tzinfo=UTC)
    old = (now - timedelta(days=100)).isoformat()
    recent = (now - timedelta(days=2)).isoformat()
    receipt_values = (
        "catalog",
        "balanced",
        "no_training",
        "general",
        "low",
        "{}",
        "[]",
        0,
        "advisor",
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO recommendation_receipts (
                   recommendation_id, created_at, catalog_version, objective, privacy,
                   task_family, difficulty, assessor_json,
                   selected_configuration_ids_json, feedback_received, advisor_version
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("old", old, *receipt_values),
        )
        connection.execute(
            """INSERT INTO recommendation_receipts (
                   recommendation_id, created_at, catalog_version, objective, privacy,
                   task_family, difficulty, assessor_json,
                   selected_configuration_ids_json, feedback_received, advisor_version
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("recent", recent, *receipt_values),
        )
    result = store.purge_older_than(30, now=now)
    assert result["receipts_deleted"] == 1
    assert store.get_receipt("old") is None
    assert store.get_receipt("recent") is not None
