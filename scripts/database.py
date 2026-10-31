"""Offline administrative backup/restore utility; never exposes a web backup endpoint.

Backup can run against a live SQLite database. Restore ONLY creates a new file.
After verifying a restored copy, stop the app, update DATABASE_PATH, then restart.
"""

import argparse
import json
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from app.backup import copy_database
from app.config import ROOT


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="Create a consistent private snapshot")
    backup.add_argument(
        "--source", type=Path, default=Path(os.getenv("DATABASE_PATH") or ROOT / "data/app.sqlite3")
    )
    backup.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser(
        "restore", help="Restore a snapshot to a NEW path; existing files are never overwritten"
    )
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = copy_database(args.source, args.output)
    except (OSError, ValueError, sqlite3.Error) as exc:
        # No rows, answers, credentials or raw SQLite internals are printed on failure.
        parser.exit(
            1,
            f"Database operation refused or failed ({type(exc).__name__}). Check the source, permissions and unused .sqlite3 destination.\n",
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
