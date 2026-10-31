"""SQLite persistence with parameterized queries and bounded-memory read paths."""

import math
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class Store:
    def __init__(self, path: str):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    question TEXT NOT NULL, answer TEXT NOT NULL, intent TEXT NOT NULL,
                    confidence REAL NOT NULL, mode TEXT NOT NULL, latency_ms INTEGER NOT NULL,
                    source_ids TEXT NOT NULL, feedback INTEGER DEFAULT NULL,
                    provider_error TEXT DEFAULT NULL
                );
                CREATE INDEX IF NOT EXISTS session_idx ON events(session_id);
                CREATE INDEX IF NOT EXISTS created_idx ON events(created_at DESC, id DESC);
            """)
            columns = {r["name"] for r in db.execute("PRAGMA table_info(events)")}
            if "provider_error" not in columns:
                db.execute("ALTER TABLE events ADD COLUMN provider_error TEXT DEFAULT NULL")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def ready(self) -> bool:
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM (SELECT id FROM events LIMIT 1)").fetchone()[0] >= 0

    def save(self, event: dict) -> None:
        with self.lock, self.connect() as db:
            db.execute(
                """INSERT INTO events
                (id,session_id,created_at,question,answer,intent,confidence,mode,latency_ms,source_ids,provider_error)
                VALUES (:id,:session_id,:created_at,:question,:answer,:intent,:confidence,:mode,:latency_ms,:source_ids,:provider_error)""",
                {"provider_error": None, **event},
            )

    def events(self, *, limit: int = 20, offset: int = 0) -> list[dict]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid pagination bounds")
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM events ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", (limit, offset)
                )
            ]

    def iter_export(self):
        """Stream a consistent read snapshot instead of loading all conversations."""
        with self.connect() as db:
            db.execute("BEGIN")
            cursor = db.execute("""SELECT id,created_at,question,answer,intent,confidence,mode,latency_ms,feedback,provider_error
                                   FROM events ORDER BY created_at DESC, id DESC""")
            while batch := cursor.fetchmany(100):
                for row in batch:
                    yield dict(row)

    def feedback(self, event_id: str, session: str, value: int) -> bool:
        with self.lock, self.connect() as db:
            return bool(
                db.execute(
                    "UPDATE events SET feedback=? WHERE id=? AND session_id=?", (value, event_id, session)
                ).rowcount
            )

    def clear(self) -> int:
        with self.lock, self.connect() as db:
            return db.execute("DELETE FROM events").rowcount

    def stats(self) -> dict:
        today = datetime.now(UTC).date().isoformat()
        with self.connect() as db:
            db.execute("BEGIN")
            result = dict(
                db.execute(
                    """SELECT COUNT(*) AS total, COUNT(DISTINCT session_id) AS sessions,
                  COALESCE(SUM(substr(created_at,1,10)=?),0) AS today,
                  COALESCE(AVG(latency_ms),0) AS avg_latency_ms,
                  COUNT(feedback) AS rated, SUM(feedback=1) AS helpful,
                  COALESCE(SUM(mode!='gemini'),0) AS fallback_count FROM events""",
                    (today,),
                ).fetchone()
            )
            result["avg_latency_ms"] = round(result["avg_latency_ms"])
            helpful = result.pop("helpful") or 0
            result["helpful_percent"] = round(100 * helpful / result["rated"]) if result["rated"] else None
            result["intents"] = {
                r["intent"]: r["n"]
                for r in db.execute("SELECT intent,COUNT(*) AS n FROM events GROUP BY intent")
            }
            result["modes"] = {
                r["mode"]: r["n"] for r in db.execute("SELECT mode,COUNT(*) AS n FROM events GROUP BY mode")
            }
            result["daily"] = [
                dict(r)
                for r in db.execute("""SELECT * FROM (
                SELECT substr(created_at,1,10) AS date, COUNT(*) AS count FROM events
                GROUP BY date ORDER BY date DESC LIMIT 30) ORDER BY date""")
            ]
            result["recent"] = [
                dict(r)
                for r in db.execute("""SELECT id,created_at,question,answer,intent,confidence,
                mode,latency_ms,feedback,provider_error FROM events ORDER BY created_at DESC,id DESC LIMIT 20""")
            ]
            n = result["total"]
            result["p95_latency_ms"] = (
                db.execute(
                    "SELECT latency_ms FROM events ORDER BY latency_ms LIMIT 1 OFFSET ?",
                    (max(0, math.ceil(n * 0.95) - 1),),
                ).fetchone()[0]
                if n
                else None
            )
            return result
