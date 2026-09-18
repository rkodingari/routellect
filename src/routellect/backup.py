from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from routellect import __version__

MAX_RESTORE_BYTES = 2 * 1024 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sqlite_snapshot(source: Path, destination: Path) -> None:
    source_uri = f"file:{source.resolve()}?mode=ro"
    with (
        sqlite3.connect(source_uri, uri=True) as source_connection,
        sqlite3.connect(destination) as destination_connection,
    ):
        source_connection.backup(destination_connection)
        result = destination_connection.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise ValueError(f"SQLite backup integrity check failed: {result}")
        destination_connection.execute("PRAGMA journal_mode = DELETE")
    destination.with_name(destination.name + "-wal").unlink(missing_ok=True)
    destination.with_name(destination.name + "-shm").unlink(missing_ok=True)


def create_backup(data_directory: Path, archive_path: Path) -> dict[str, object]:
    source = data_directory.resolve()
    archive = archive_path.resolve()
    if archive.exists():
        raise FileExistsError(f"backup already exists: {archive}")
    if archive == source or source in archive.parents:
        raise ValueError("backup archive must be outside the data directory")
    archive.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="routellect-backup-") as temporary:
        staging = Path(temporary) / "data"
        staging.mkdir()
        database = source / "routellect.sqlite3"
        if database.exists():
            _sqlite_snapshot(database, staging / database.name)
        if source.exists():
            for path in source.rglob("*"):
                relative = path.relative_to(source)
                if path.is_symlink():
                    raise ValueError(f"refusing to back up symlink: {relative}")
                if path.is_dir():
                    continue
                if not path.is_file():
                    raise ValueError(f"unsupported data entry: {relative}")
                if relative.as_posix() in {
                    "routellect.sqlite3",
                    "routellect.sqlite3-wal",
                    "routellect.sqlite3-shm",
                }:
                    continue
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)

        files = [path for path in sorted(staging.rglob("*")) if path.is_file()]
        manifest = {
            "format": "routellect-backup-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "routellect_version": __version__,
            "files": [
                {
                    "path": path.relative_to(staging).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in files
            ],
        }
        manifest_path = Path(temporary) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(manifest_path, arcname="manifest.json", recursive=False)
            for path in files:
                tar.add(path, arcname=f"data/{path.relative_to(staging).as_posix()}")
    return {
        **manifest,
        "archive": str(archive),
        "archive_sha256": _sha256(archive),
    }


def _safe_member_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe backup member: {name}")
    return path


def restore_backup(archive_path: Path, target_directory: Path) -> dict[str, object]:
    archive = archive_path.resolve()
    target = target_directory.resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"backup does not exist: {archive}")
    if target.exists() and any(target.iterdir()):
        raise FileExistsError("restore target must be empty")
    target.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        total_size = sum(member.size for member in members)
        if total_size > MAX_RESTORE_BYTES:
            raise ValueError("backup exceeds the restore size limit")
        by_name = {_safe_member_name(member.name).as_posix(): member for member in members}
        if len(by_name) != len(members) or "manifest.json" not in by_name:
            raise ValueError("backup has duplicate members or no manifest")
        if any(not member.isfile() for member in members):
            raise ValueError("backup may contain regular files only")
        manifest_file = tar.extractfile(by_name["manifest.json"])
        if manifest_file is None:
            raise ValueError("backup manifest is unreadable")
        manifest = json.load(manifest_file)
        if manifest.get("format") != "routellect-backup-v1":
            raise ValueError("unsupported backup format")
        declared = manifest.get("files")
        if not isinstance(declared, list):
            raise ValueError("backup file manifest is invalid")
        declared_paths: list[str] = []
        for item in declared:
            if not isinstance(item, dict):
                raise ValueError("backup file manifest is invalid")
            item_path = item.get("path")
            if not isinstance(item_path, str) or not item_path:
                raise ValueError("backup file manifest is invalid")
            relative = _safe_member_name(item_path)
            if not isinstance(item.get("size"), int) or not isinstance(
                item.get("sha256"), str
            ):
                raise ValueError("backup file manifest is invalid")
            declared_paths.append(relative.as_posix())
        if len(set(declared_paths)) != len(declared_paths):
            raise ValueError("backup file manifest contains duplicate paths")
        expected_members = {"manifest.json"} | {
            f"data/{path}" for path in declared_paths
        }
        if set(by_name) != expected_members:
            raise ValueError("backup contents do not match its manifest")

        with tempfile.TemporaryDirectory(
            prefix=".routellect-restore-", dir=target.parent
        ) as temporary:
            restored = Path(temporary) / "restored"
            restored.mkdir(mode=0o700)
            for item in declared:
                if not isinstance(item, dict):
                    raise ValueError("backup file manifest is invalid")
                relative = _safe_member_name(str(item.get("path", "")))
                member = by_name[f"data/{relative.as_posix()}"]
                source_handle = tar.extractfile(member)
                if source_handle is None:
                    raise ValueError(f"backup member is unreadable: {relative}")
                destination = restored.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with destination.open("xb") as output:
                    shutil.copyfileobj(source_handle, output)
                os.chmod(destination, 0o600)
                if destination.stat().st_size != int(item.get("size", -1)):
                    raise ValueError(f"size mismatch for restored file: {relative}")
                if _sha256(destination) != item.get("sha256"):
                    raise ValueError(f"digest mismatch for restored file: {relative}")
            database = restored / "routellect.sqlite3"
            if database.exists():
                with sqlite3.connect(database) as connection:
                    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    raise ValueError(f"restored SQLite integrity check failed: {result}")
            if target.exists():
                target.rmdir()
            os.replace(restored, target)
    return {
        "format": manifest["format"],
        "created_at": manifest["created_at"],
        "restored_files": len(manifest["files"]),
        "archive_sha256": _sha256(archive),
        "target": str(target),
    }
