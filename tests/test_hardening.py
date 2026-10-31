import asyncio
import csv
import io
import sqlite3
import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.diagnostics import ProviderStatus
from app.limits import RateLimiter
from app.main import create_app
from app.ml import Models
from app.privacy import spreadsheet_safe
from app.provider import ProviderError
from app.store import Store

AUTH = {"Authorization": "Bearer test-secret"}


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(settings=Settings(admin_token="test-secret", database_path=str(tmp_path / "test.sqlite3")))
    ) as c:
        yield c


def ask(client, message="How do I apply for admission?"):
    return client.post("/api/chat", json={"message": message, "session_id": str(uuid.uuid4())})


@pytest.mark.parametrize(
    "url", ["/api/analytics", "/api/conversations", "/api/export", "/api/provider/status"]
)
def test_all_private_reads_require_bearer(client, url):
    for header in ["", "test-secret", "Basic test-secret", "Bearer wrong"]:
        response = client.get(url, headers={"Authorization": header})
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("method,url", [("post", "/api/provider/check"), ("delete", "/api/conversations")])
def test_private_mutations_require_bearer(client, method, url):
    assert getattr(client, method)(url).status_code == 401


def test_body_limit(client):
    response = client.post("/api/chat", content=b"x" * 20000, headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_streamed_body_without_content_length(client):
    response = client.post(
        "/api/chat", content=iter([b"x" * 10000, b"x" * 10000]), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_unknown_fields_and_no_validation_echo(client):
    response = client.post(
        "/api/chat", json={"message": "secret", "session_id": str(uuid.uuid4()), "api_key": "DO_NOT_ECHO"}
    )
    assert response.status_code == 422
    assert "DO_NOT_ECHO" not in response.text


@pytest.mark.parametrize("rating", [True, False, 1.0, "1", None, 2, -2])
def test_strict_feedback_rating(client, rating):
    response = client.post(
        "/api/feedback/" + str(uuid.uuid4()), json={"session_id": str(uuid.uuid4()), "value": rating}
    )
    assert response.status_code == 422


def test_readiness(client, monkeypatch):
    assert client.get("/api/ready").json()["status"] == "ready"

    def fail():
        raise sqlite3.OperationalError("internal path and credentials")

    monkeypatch.setattr(client.app.state.store, "ready", fail)
    result = client.get("/api/ready")
    assert result.status_code == 503 and "internal" not in result.text


def test_storage_failure_is_not_success(client, monkeypatch):
    def fail(*args):
        raise sqlite3.OperationalError("private internal path")

    monkeypatch.setattr(client.app.state.store, "save", fail)
    result = ask(client)
    assert result.status_code == 503
    assert "private" not in result.text


def test_pagination(client):
    ids = [ask(client).json()["id"] for _ in range(3)]
    items = client.get("/api/conversations?limit=2&offset=1", headers=AUTH).json()["items"]
    assert [item["id"] for item in items] == ids[-2::-1]
    assert all("session_id" not in item for item in items)
    for query in ["limit=0", "limit=101", "offset=-1", "offset=1000001"]:
        assert client.get("/api/conversations?" + query, headers=AUTH).status_code == 422


def test_empty_export_is_valid_csv(client):
    response = client.get("/api/export", headers=AUTH)
    reader = csv.DictReader(io.StringIO(response.text))
    assert list(reader) == [] and "question" in reader.fieldnames


def test_no_sources_never_call_gemini(client, monkeypatch):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="fake")

    async def forbidden(*args, **kwargs):
        raise AssertionError("No sources must not trigger external generation")

    monkeypatch.setattr("app.provider.generate_answer", forbidden)
    assert ask(client, "zyxqw qqqzz").json()["mode"] == "no_match"


@pytest.mark.parametrize(
    "code",
    [
        "authentication",
        "model_unavailable",
        "quota",
        "timeout",
        "network",
        "blocked",
        "truncated",
        "upstream",
    ],
)
def test_typed_fallbacks_and_diagnostics(client, monkeypatch, code):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="fake")
    calls = []

    async def fail(*args, **kwargs):
        calls.append(True)
        raise ProviderError(code)

    monkeypatch.setattr("app.provider.generate_answer", fail)
    result = ask(client).json()
    assert result["mode"] == "retrieval" and result["provider_error"] == code
    status = client.get("/api/provider/status", headers=AUTH).json()
    assert status["last_error"] == code
    assert status["successes"] == 0 and status["failures"] == 1
    ask(client)
    assert len(calls) == (1 if code in {"authentication", "model_unavailable", "quota"} else 2)


def test_admin_check_without_key(client):
    row = client.post("/api/provider/check", headers=AUTH).json()
    assert row["ok"] is False and row["error"] == "not_configured"
    assert client.get("/api/analytics", headers=AUTH).json()["total"] == 0


def test_admin_check_and_rate_limit(client, monkeypatch):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="fake")

    async def answer(*args, **kwargs):
        return "Sample school hours are illustrative."

    monkeypatch.setattr("app.provider.generate_answer", answer)
    for _ in range(3):
        assert client.post("/api/provider/check", headers=AUTH).json()["ok"] is True
    blocked = client.post("/api/provider/check", headers=AUTH)
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    assert client.get("/api/analytics", headers=AUTH).json()["total"] == 0


def test_admin_check_provider_failure(client, monkeypatch):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="fake")

    async def fail(*args, **kwargs):
        raise ProviderError("model_unavailable")

    monkeypatch.setattr("app.provider.generate_answer", fail)
    assert client.post("/api/provider/check", headers=AUTH).json()["error"] == "model_unavailable"


def test_generation_queue_is_bounded(client):
    client.app.state.settings = replace(client.app.state.settings, gemini_key="fake", queue_timeout=0.01)
    client.app.state.semaphore = asyncio.Semaphore(0)
    row = ask(client).json()
    assert row["mode"] == "retrieval" and row["provider_error"] == "busy"


def test_rate_window_and_bounded_clients():
    current = [0.0]
    limiter = RateLimiter(2, max_clients=2, clock=lambda: current[0])
    assert limiter.check("one") == 0
    assert limiter.check("one") == 0
    assert limiter.check("one") == 60
    current[0] = 60.0
    assert limiter.check("one") == 0
    limiter.check("two")
    limiter.check("three")
    assert len(limiter.clients) == 2


def test_provider_status_reset():
    status = ProviderStatus()
    status.failure("quota")
    assert status.cooldown() == "quota"
    status.success()
    assert status.cooldown() is None and status.last_error is None


@pytest.mark.parametrize("value", ["=1+1", " +CMD()", "\t@SUM(A1)", "\r-1", "  =x"])
def test_formula_neutralization(value):
    assert spreadsheet_safe(value) == "'" + value


@pytest.mark.parametrize("value", ["plain text", "", None, 42])
def test_csv_safe_values_unchanged(value):
    assert spreadsheet_safe(value) == value


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model": "../unsafe"},
        {"model": "https://bad"},
        {"provider_timeout": 0},
        {"queue_timeout": 0},
        {"chat_rate_limit": 0},
        {"provider_concurrency": 0},
        {"database_path": ""},
    ],
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_secrets_absent_from_settings_repr():
    assert "private-key" not in repr(Settings(gemini_key="private-key", admin_token="private-key"))


def test_existing_database_migration(tmp_path):
    path = tmp_path / "old.sqlite3"
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE events (id TEXT PRIMARY KEY,session_id TEXT NOT NULL,created_at TEXT NOT NULL,
    question TEXT NOT NULL,answer TEXT NOT NULL,intent TEXT NOT NULL,confidence REAL NOT NULL,mode TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,source_ids TEXT NOT NULL,feedback INTEGER DEFAULT NULL)""")
    db.commit()
    db.close()
    store = Store(str(path))
    assert store.ready()
    assert store.stats()["total"] == 0
    with store.connect() as db:
        assert "provider_error" in [r["name"] for r in db.execute("PRAGMA table_info(events)")]


def test_all_faqs_retrieve_themselves():
    models = Models()
    for faq in models.faqs:
        assert models.retrieve(faq["question"])[0]["id"] == faq["id"]


def test_empty_analytics(client):
    row = client.get("/api/analytics", headers=AUTH).json()
    assert row["total"] == 0 and row["helpful_percent"] is None and row["p95_latency_ms"] is None
    assert row["daily"] == [] and row["intents"] == {} and row["modes"] == {}


def test_security_headers_and_auth_schema(client):
    response = client.get("/")
    uuid.UUID(response.headers["X-Request-ID"])
    assert response.headers["Cache-Control"] == "no-store"
    assert "camera=()" in response.headers["Permissions-Policy"]
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/api/analytics"]["get"]["security"]


def test_all_faq_intents_match_categories():
    models = Models()
    for faq in models.faqs:
        assert models.classify(faq["question"])[0] == faq["category"]
