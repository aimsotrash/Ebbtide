"""Minimum-viable backup utility for Dory.md's two on-disk stores (P0 storage
readiness).

Snapshots, into a single timestamped directory:
  - SQLite: via the online backup API (`sqlite3.Connection.backup`). This is
    safe to run while the server is live and is WAL-aware — it produces a
    single consistent .db file with no -wal/-shm sidecars.
  - ChromaDB: a tar.gz of the persistence directory.

Path resolution mirrors the app (same env vars), so a backup taken from the
deployment environment lands on the same data the API uses:
  DORY_DB_PATH      (default: backend/data/dory.db)
  DORY_CHROMA_PATH  (default: backend/data/chroma)
  DORY_BACKUP_DIR   (default: backend/data/backups)

Usage:
  cd backend
  python -m scripts.backup                 # uses the env / defaults above
  python -m scripts.backup --out /mnt/backups
  python -m scripts.backup --db /data/dory.db --chroma /data/chroma --out /backups
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import tarfile
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def default_db_path() -> Path:
    override = os.getenv("DORY_DB_PATH")
    return Path(override) if override else _BACKEND_ROOT / "data" / "dory.db"


def default_chroma_path() -> Path:
    override = os.getenv("DORY_CHROMA_PATH")
    return Path(override) if override else _BACKEND_ROOT / "data" / "chroma"


def default_backup_dir() -> Path:
    override = os.getenv("DORY_BACKUP_DIR")
    return Path(override) if override else _BACKEND_ROOT / "data" / "backups"


def backup_sqlite(src: Path, dst: Path) -> Path:
    """Consistent, WAL-safe snapshot of the SQLite DB using the online backup
    API. Returns the destination path. Raises FileNotFoundError if src is absent."""
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"SQLite database not found: {src}")
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(str(src))
    try:
        dest = sqlite3.connect(str(dst))
        try:
            source.backup(dest)  # atomic, copies committed + WAL state
        finally:
            dest.close()
    finally:
        source.close()
    return dst


def backup_chroma(src_dir: Path, dst_tar: Path) -> Path | None:
    """tar.gz the Chroma directory. Returns the archive path, or None if the
    directory does not exist yet (no vectors stored)."""
    src_dir = Path(src_dir)
    if not src_dir.exists():
        return None
    dst_tar = Path(dst_tar)
    dst_tar.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dst_tar, "w:gz") as tar:
        tar.add(src_dir, arcname=src_dir.name)
    return dst_tar


def run_backup(
    out_dir: Path | str | None = None,
    db_path: Path | str | None = None,
    chroma_path: Path | str | None = None,
) -> dict:
    """Take a full snapshot into a timestamped sub-directory of out_dir.
    Returns a manifest dict with the resolved paths."""
    db = Path(db_path) if db_path else default_db_path()
    chroma = Path(chroma_path) if chroma_path else default_chroma_path()
    base = Path(out_dir) if out_dir else default_backup_dir()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = base / stamp
    target.mkdir(parents=True, exist_ok=True)

    sqlite_dst = backup_sqlite(db, target / "dory.db") if db.exists() else None
    chroma_dst = backup_chroma(chroma, target / "chroma.tar.gz")

    return {
        "timestamp": stamp,
        "backup_dir": str(target),
        "sqlite": str(sqlite_dst) if sqlite_dst else None,
        "chroma": str(chroma_dst) if chroma_dst else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up Dory.md SQLite + Chroma stores.")
    parser.add_argument("--out", help="Backup output directory (default: $DORY_BACKUP_DIR or backend/data/backups)")
    parser.add_argument("--db", help="SQLite path (default: $DORY_DB_PATH or backend/data/dory.db)")
    parser.add_argument("--chroma", help="Chroma dir (default: $DORY_CHROMA_PATH or backend/data/chroma)")
    args = parser.parse_args()

    manifest = run_backup(out_dir=args.out, db_path=args.db, chroma_path=args.chroma)
    print("Backup complete:")
    for key, value in manifest.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
