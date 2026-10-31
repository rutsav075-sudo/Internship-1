"""Consistent SQLite snapshots and non-overwriting restore to a new database file.

Backups contain private conversation data; this is not encryption or secure erasure.
"""

import os
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path


def copy_database(source: Path, destination: Path, *, max_seconds: float = 30) -> dict:
    """Copy with SQLite's online backup API, then publish atomically without overwriting.

    The source is opened read-only, the copy is integrity checked, and the final file
    is owner-readable/writable only on POSIX. Callers must protect the parent directory.
    Existing destinations, symlinks and same-path copies are deliberately refused.
    """
    if max_seconds <= 0:
        raise ValueError("Backup timeout must be positive")
    deadline = time.monotonic() + max_seconds

    def progress(status, remaining, total):
        if time.monotonic() >= deadline:
            raise TimeoutError("Database snapshot exceeded its time budget")

    source = Path(source).resolve(strict=True)
    destination = Path(destination).absolute()
    if not source.is_file():
        raise ValueError("Source must be a database file")
    if destination.suffix != ".sqlite3":
        raise ValueError("Destination must end in .sqlite3 to keep backup exclusion rules reliable")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Refusing to overwrite an existing database or symlink")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".sqlite3-backup-", suffix=".tmp", dir=destination.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as original:
            original.execute("PRAGMA query_only=ON")
            columns = {row[1] for row in original.execute("PRAGMA table_info(events)")}
            if not {"id", "session_id", "question", "answer", "feedback"}.issubset(columns):
                raise ValueError("Source is not an Edxso conversation database")
            with closing(sqlite3.connect(str(temporary))) as target:
                original.backup(target, pages=256, sleep=0.05, progress=progress)
                target.commit()
                integrity = target.execute("PRAGMA quick_check").fetchone()[0]
                if integrity != "ok":
                    raise ValueError("Database copy failed its integrity check")
                count = target.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                # A standalone snapshot must not depend on transient WAL sidecars.
                target.execute("PRAGMA journal_mode=DELETE")
        temporary.chmod(0o600)
        # fsync the snapshot before publication. os.link is same-filesystem atomic and
        # fails if the destination appeared after the existence check (no replace race).
        with temporary.open("rb") as snapshot:
            os.fsync(snapshot.fileno())
        os.link(temporary, destination)
        return {"status": "ok", "integrity": integrity, "records": count, "destination": str(destination)}
    finally:
        temporary.unlink(missing_ok=True)
        Path(str(temporary) + "-wal").unlink(missing_ok=True)
        Path(str(temporary) + "-shm").unlink(missing_ok=True)
        Path(str(temporary) + "-journal").unlink(missing_ok=True)
