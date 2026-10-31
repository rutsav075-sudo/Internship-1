import csv
import io
import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.ml import Models, evaluate
from app.privacy import redact
from app.provider import ProviderError


@pytest.fixture
def client(tmp_path):
    config = Settings(database_path=str(tmp_path / "test.sqlite3"), admin_token="test-secret")
    with TestClient(create_app(settings=config)) as c:
        yield c


AUTH = {"Authorization": "Bearer test-secret"}


def ask(client, message="How do I apply for admission?", session=None):
    return client.post("/api/chat", json={"message": message, "session_id": session or str(uuid.uuid4())})


def test_health_and_static(client):
    assert client.get("/api/health").json()["provider_configured"] is False
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "Edxso Education AI"
    assert client.get("/static/app.js").status_code == 200
    assert "nosniff" == client.get("/").headers["X-Content-Type-Options"]


def test_knowledge(client):
    rows = client.get("/api/knowledge").json()
    assert len(rows) == 8
    assert len({r["id"] for r in rows}) == 8


def test_chat_retrieval_and_storage(client):
    response = ask(client)
    assert response.status_code == 200
    row = response.json()
    assert row["mode"] == "retrieval"
    assert row["sources"][0]["id"] == "admissions"
    assert "not configured" in row["notice"]
    stats = client.get("/api/analytics", headers=AUTH).json()
    assert stats["total"] == 1 and stats["sessions"] == 1
    assert stats["recent"][0]["id"] == row["id"]
    assert stats["fallback_count"] == 1


def test_no_match(client):
    row = ask(client, "zyxqwv qqqzz").json()
    assert row["mode"] == "no_match" and row["sources"] == []


def test_validation(client):
    for message in [" ", "x", "x" * 2001, "hi\x00there"]:
        assert ask(client, message).status_code == 422
    assert client.post("/api/chat", json={"message": "hello", "session_id": "invalid"}).status_code == 422


def test_private_routes(client, monkeypatch):
    assert client.get("/api/analytics").status_code == 401
    assert client.get("/api/export").status_code == 401
    assert client.delete("/api/conversations").status_code == 401
    assert client.get("/api/analytics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    client.app.state.settings = replace(client.app.state.settings, admin_token="")
    assert client.get("/api/analytics", headers=AUTH).status_code == 401


def test_feedback_ownership(client):
    session = str(uuid.uuid4())
    row = ask(client, session=session).json()
    assert (
        client.post(
            "/api/feedback/" + row["id"], json={"session_id": str(uuid.uuid4()), "value": 1}
        ).status_code
        == 404
    )
    assert (
        client.post("/api/feedback/" + row["id"], json={"session_id": session, "value": 0}).status_code == 422
    )
    for value in [1, -1, 1]:
        assert (
            client.post(
                "/api/feedback/" + row["id"], json={"session_id": session, "value": value}
            ).status_code
            == 200
        )
    stats = client.get("/api/analytics", headers=AUTH).json()
    assert stats["rated"] == 1 and stats["helpful_percent"] == 100


def test_export_and_delete(client):
    ask(client, "= How do I apply for admission?")
    response = client.get("/api/export", headers=AUTH)
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0]["question"].startswith("'=")
    assert "session_id" not in rows[0]
    assert client.delete("/api/conversations", headers=AUTH).status_code == 200
    assert client.get("/api/analytics", headers=AUTH).json()["total"] == 0


def test_rate_limit(client):
    for _ in range(20):
        assert ask(client).status_code == 200
    assert ask(client).status_code == 429


def test_pii_redaction(client):
    raw = "Contact me at person@example.com or +91 98765 43210 about fees"
    ask(client, raw)
    stored = client.get("/api/analytics", headers=AUTH).json()["recent"][0]
    assert "person@example.com" not in stored["question"]
    assert "98765" not in stored["question"]
    assert "[email removed]" in redact(raw)


def test_gemini_success(client, monkeypatch):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="fake-key")

    async def fake(key, model, message, sources, **kwargs):
        assert key == "fake-key" and len(sources) > 0
        assert "person@example.com" not in message
        return "A grounded sample answer."

    monkeypatch.setattr("app.provider.generate_answer", fake)
    row = ask(client, "What are the fees? Email person@example.com").json()
    assert row["mode"] == "gemini" and row["notice"] is None
    assert row["answer"] == "A grounded sample answer."


def test_gemini_failure_fallback(client, monkeypatch):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="fake-key")

    async def fail(*args, **kwargs):
        raise ProviderError("authentication")

    monkeypatch.setattr("app.provider.generate_answer", fail)
    row = ask(client).json()
    assert row["mode"] == "retrieval" and "unavailable" in row["notice"]
    assert "private" not in str(row)


def test_evaluation(client):
    report = client.get("/api/evaluation").json()
    assert report["train_samples"] == 120 and report["test_samples"] == 15
    assert report == evaluate()
    assert sum(map(sum, report["confusion_matrix"])) == 15
    assert 0 <= report["macro_f1"] <= 1


@pytest.mark.parametrize(
    "question,label",
    [
        ("How do I apply for admission?", "Admissions"),
        ("What are the school fees?", "Fees"),
        ("Is there a school bus?", "Transport"),
        ("Which curriculum do you follow?", "Academics"),
        ("I need to speak to a person", "Support"),
    ],
)
def test_classifier(question, label):
    actual, score = Models().classify(question)
    assert actual == label and 0 <= score <= 1
