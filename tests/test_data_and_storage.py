import json
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from app import ml
from app.config import Settings
from app.main import create_app
from app.store import Store


@pytest.fixture
def sample_data_dir(tmp_path, monkeypatch):
    directory = tmp_path / "data"
    directory.mkdir()
    monkeypatch.setattr(ml, "ROOT", tmp_path)
    return directory


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"Wrong": ["a", "b", "c", "d"]},
        {label: [] for label in ml.LABELS},
        {label: ["Good example", "Another example", "Third example", None] for label in ml.LABELS},
        {label: ["Same", "Same", "Third", "Fourth"] for label in ml.LABELS},
    ],
)
def test_invalid_training_data_rejected(sample_data_dir, payload):
    (sample_data_dir / "training.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        ml.read_examples("training.json")


def test_augmented_data_cannot_overlap_original(sample_data_dir):
    payload = {label: [f"{label} original example {i}" for i in range(4)] for label in ml.LABELS}
    for name in ["training.json", "augmentation.json"]:
        (sample_data_dir / name).write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="duplicate"):
        ml.dataset()


@pytest.mark.parametrize(
    "faqs",
    [
        [],
        [
            {
                "id": "same",
                "category": "Admissions",
                "question": "Question",
                "answer": "Answer",
                "keywords": "keyword",
            },
            {
                "id": "same",
                "category": "Fees",
                "question": "Other question",
                "answer": "Other answer",
                "keywords": "another",
            },
        ],
    ],
)
def test_empty_or_duplicate_knowledge_rejected(monkeypatch, faqs):
    original = ml.json.loads

    def loads(text, *args, **kwargs):
        result = original(text, *args, **kwargs)
        return faqs if isinstance(result, list) else result

    monkeypatch.setattr(ml.json, "loads", loads)
    with pytest.raises(ValueError, match="Knowledge"):
        ml.Models()


def test_invalid_pagination_rejected(tmp_path):
    store = Store(str(tmp_path / "db.sqlite3"))
    for args in [{"limit": 0}, {"limit": 101}, {"offset": -1}]:
        with pytest.raises(ValueError):
            store.events(**args)


def test_transactions_rollback(tmp_path):
    store = Store(str(tmp_path / "db.sqlite3"))
    with pytest.raises(sqlite3.OperationalError), store.connect() as db:
        db.execute("CREATE TABLE sample(value INTEGER)")
        db.execute("INSERT INTO sample VALUES (1)")
        db.execute("INSERT INTO missing_table VALUES (1)")
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 0


def test_store_aggregations_use_all_events_but_bound_recent(tmp_path):
    store = Store(str(tmp_path / "db.sqlite3"))
    session = str(uuid.uuid4())
    for i in range(25):
        store.save(
            {
                "id": str(uuid.uuid4()),
                "session_id": session,
                "created_at": f"2026-01-01T00:00:{i:02d}+00:00",
                "question": "A sample question",
                "answer": "Sample answer",
                "intent": "Fees",
                "confidence": 0.5,
                "mode": "gemini" if i % 2 else "retrieval",
                "latency_ms": i * 10,
                "source_ids": "[]",
            }
        )
    result = store.stats()
    assert result["total"] == 25 and len(result["recent"]) == 20 and result["sessions"] == 1
    assert result["avg_latency_ms"] == 120 and result["p95_latency_ms"] == 230
    assert result["fallback_count"] == 13 and result["modes"] == {"gemini": 12, "retrieval": 13}
    assert len(list(store.iter_export())) == 25
    assert store.clear() == 25


def test_legacy_db_path_constructor(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "path.sqlite3", settings=Settings())) as client:
        assert client.get("/api/ready").status_code == 200
