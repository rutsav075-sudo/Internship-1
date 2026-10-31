import os
import sqlite3
import uuid
from contextlib import closing
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.backup import copy_database
from app.config import Settings
from app.main import create_app
from app.store import Store

AUTH = {"Authorization": "Bearer test-secret"}


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(settings=Settings(database_path=str(tmp_path / "test.sqlite3"), admin_token="test-secret"))
    ) as c:
        yield c


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "source.sqlite3"
    store = Store(str(path))
    event_id = str(uuid.uuid4())
    session = str(uuid.uuid4())
    store.save(
        {
            "id": event_id,
            "session_id": session,
            "created_at": "2026-10-31T00:00:00+00:00",
            "question": "Synthetic backup check",
            "answer": "Sample response",
            "intent": "Support",
            "confidence": 0.5,
            "mode": "retrieval",
            "latency_ms": 123,
            "source_ids": "[]",
        }
    )
    store.feedback(event_id, session, 1)
    return path, store, event_id


def test_operations_requires_admin(client):
    assert client.get("/api/operations").status_code == 401


def test_operations_empty_no_key(client):
    result = client.get("/api/operations", headers=AUTH).json()
    assert result["application"]["status"] == "ready"
    assert result["database"] == {"engine": "SQLite", "connected": True}
    assert result["model"]["serving_samples"] == 135
    assert result["provider"]["state"] == "unconfigured"
    assert result["traffic"]["fallback_percent"] is None
    assert result["traffic"]["average_latency_ms"] is None
    assert result["warnings"]
    assert "test-secret" not in str(result)
    assert "database_path" not in str(result)


def test_operations_unverified_and_verified(client):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="private-test-key")
    result = client.get("/api/operations", headers=AUTH).json()
    assert result["provider"]["state"] == "unverified"
    client.app.state.provider_status.success()
    result = client.get("/api/operations", headers=AUTH).json()
    assert result["provider"]["state"] == "verified"
    assert "private-test-key" not in str(result)
    assert len(result["warnings"]) == 1


def test_operations_error_and_traffic(client):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="private-test-key")
    # Unmatched questions deliberately bypass generation while still persisting traffic.
    client.post("/api/chat", json={"message": "zyxqwv qqqzz", "session_id": str(uuid.uuid4())})
    client.app.state.provider_status.failure("quota")
    result = client.get("/api/operations", headers=AUTH).json()
    assert result["provider"]["state"] == "error"
    assert result["traffic"]["fallback_percent"] == 100
    assert result["traffic"]["answer_modes"] == {"no_match": 1}
    assert result["traffic"]["p95_latency_ms"] is not None


def test_operations_storage_failure_sanitized(client, monkeypatch):
    def fail():
        raise sqlite3.OperationalError("internal database detail")

    monkeypatch.setattr(client.app.state.store, "ready", fail)
    result = client.get("/api/operations", headers=AUTH)
    assert result.status_code == 503 and "internal" not in result.text


def test_provider_diagnostic_handles_one_reordered_reference(client, monkeypatch):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="fake")
    reference = client.app.state.models.faqs[-1]
    client.app.state.models.faqs = [reference]

    async def fake(key, model, message, sources, **kwargs):
        assert message == reference["question"]
        assert sources == [reference]
        return "An illustrative answer."

    monkeypatch.setattr("app.provider.generate_answer", fake)
    assert client.post("/api/provider/check", headers=AUTH).json()["ok"] is True


def test_backup_restore_preserves_rows_and_feedback(database, tmp_path):
    source, store, event_id = database
    backup = tmp_path / "private" / "backup.sqlite3"
    copied = copy_database(source, backup)
    assert copied["status"] == "ok" and copied["records"] == 1 and copied["integrity"] == "ok"
    # Prove a restored database is independent from changes after the backup.
    store.clear()
    restored = tmp_path / "restored.sqlite3"
    copy_database(backup, restored)
    reopened = Store(str(restored))
    assert reopened.stats()["total"] == 1
    assert reopened.events()[0]["id"] == event_id
    assert reopened.events()[0]["feedback"] == 1
    assert store.stats()["total"] == 0
    if os.name == "posix":
        assert backup.stat().st_mode & 0o777 == 0o600
    assert not list(backup.parent.glob(".sqlite3-backup-*"))


def test_backup_refuses_existing_destination(database, tmp_path):
    source, _, _ = database
    output = tmp_path / "existing.sqlite3"
    output.write_bytes(b"leave me unchanged")
    with pytest.raises(FileExistsError):
        copy_database(source, output)
    assert output.read_bytes() == b"leave me unchanged"


def test_backup_refuses_same_path(database):
    source, store, _ = database
    with pytest.raises(FileExistsError):
        copy_database(source, source)
    assert store.stats()["total"] == 1


def test_backup_refuses_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        copy_database(tmp_path / "missing.sqlite3", tmp_path / "new.sqlite3")
    assert not (tmp_path / "new.sqlite3").exists()


def test_backup_refuses_wrong_extension(database, tmp_path):
    source, _, _ = database
    with pytest.raises(ValueError, match="sqlite3"):
        copy_database(source, tmp_path / "backup.txt")


def test_backup_refuses_directory_source(tmp_path):
    with pytest.raises(ValueError, match="file"):
        copy_database(tmp_path, tmp_path / "new.sqlite3")


def test_backup_refuses_symlink_destination(database, tmp_path):
    source, _, _ = database
    output = tmp_path / "link.sqlite3"
    output.symlink_to(tmp_path / "missing-target.sqlite3")
    with pytest.raises(FileExistsError):
        copy_database(source, output)


def test_backup_rejects_foreign_database_and_cleans_temp(tmp_path):
    source = tmp_path / "foreign.sqlite3"
    with closing(sqlite3.connect(str(source))) as db:
        db.execute("CREATE TABLE unrelated(id INTEGER)")
        db.commit()
    with pytest.raises(ValueError, match="Edxso"):
        copy_database(source, tmp_path / "result.sqlite3")
    assert not (tmp_path / "result.sqlite3").exists()
    assert not list(tmp_path.glob(".sqlite3-backup-*"))


def test_backup_refuses_atomic_publish_race(database, tmp_path, monkeypatch):
    source, store, _ = database

    def collision(*args):
        raise FileExistsError("destination appeared")

    monkeypatch.setattr("app.backup.os.link", collision)
    with pytest.raises(FileExistsError):
        copy_database(source, tmp_path / "new.sqlite3")
    assert not list(tmp_path.glob(".sqlite3-backup-*"))
    assert store.stats()["total"] == 1


def test_backup_has_a_positive_deadline(database, tmp_path):
    source, _, _ = database
    with pytest.raises(ValueError, match="positive"):
        copy_database(source, tmp_path / "new.sqlite3", max_seconds=0)


def test_backup_deadline_cleans_up(database, tmp_path, monkeypatch):
    source, store, _ = database
    clock = iter([0.0, 100.0])
    monkeypatch.setattr("app.backup.time.monotonic", lambda: next(clock))
    with pytest.raises(TimeoutError):
        copy_database(source, tmp_path / "new.sqlite3", max_seconds=1)
    assert not (tmp_path / "new.sqlite3").exists()
    assert not list(tmp_path.glob(".sqlite3-backup-*"))
    assert store.stats()["total"] == 1


def test_database_cli_backup_and_restore(database, tmp_path, monkeypatch, capsys):
    from scripts.database import main

    source, _, _ = database
    backup = tmp_path / "cli-backup.sqlite3"
    monkeypatch.setattr("sys.argv", ["database", "backup", "--source", str(source), "--output", str(backup)])
    main()
    assert '"status": "ok"' in capsys.readouterr().out
    restored = tmp_path / "cli-restored.sqlite3"
    monkeypatch.setattr(
        "sys.argv", ["database", "restore", "--source", str(backup), "--output", str(restored)]
    )
    main()
    assert Store(str(restored)).stats()["total"] == 1


def test_database_cli_failure_does_not_echo_sqlite_details(tmp_path, monkeypatch, capsys):
    from scripts.database import main

    monkeypatch.setattr(
        "sys.argv",
        [
            "database",
            "backup",
            "--source",
            str(tmp_path / "missing.sqlite3"),
            "--output",
            str(tmp_path / "unused.sqlite3"),
        ],
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 1
    assert "FileNotFoundError" in capsys.readouterr().err
