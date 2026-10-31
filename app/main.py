"""Application composition and API endpoints. Run with uvicorn app.main:app."""

import asyncio
import csv
import io
import json
import logging
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import provider
from .config import ROOT, Settings
from .diagnostics import ProviderStatus
from .limits import RateLimiter, RequestSizeLimit
from .ml import Models, evaluate
from .monitoring import operations_snapshot
from .privacy import redact, spreadsheet_safe
from .schemas import FAQ, ChatRequest, ChatResponse, FeedbackRequest
from .store import Store

log = logging.getLogger("edxso")
bearer = HTTPBearer(auto_error=False)
CSV_FIELDS = [
    "id",
    "created_at",
    "question",
    "answer",
    "intent",
    "confidence",
    "mode",
    "latency_ms",
    "feedback",
    "provider_error",
]


def create_app(db_path=None, *, settings: Settings | None = None):
    if settings is None:
        # Explicit app construction reads .env; importing utility modules has no secret-loading side effects.
        load_dotenv(ROOT / ".env", override=False)
        settings = Settings.from_env()
    if db_path is not None:
        from dataclasses import replace

        settings = replace(settings, database_path=str(db_path))

    @asynccontextmanager
    async def lifespan(app):
        app.state.started_at = time.monotonic()
        app.state.settings = settings
        app.state.models = Models()
        app.state.evaluation = evaluate()
        app.state.store = Store(settings.database_path)
        app.state.limiter = RateLimiter(settings.chat_rate_limit)
        app.state.check_limiter = RateLimiter(3)
        app.state.semaphore = asyncio.Semaphore(settings.provider_concurrency)
        app.state.provider_status = ProviderStatus()
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.provider_timeout, connect=5),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=settings.provider_concurrency),
        ) as client:
            app.state.provider_client = client
            yield

    app = FastAPI(
        title="Edxso Education AI", version="1.2.0", lifespan=lifespan, docs_url=None, redoc_url=None
    )
    app.add_middleware(RequestSizeLimit, maximum=settings.max_request_bytes)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'self'; form-action 'self'; object-src 'none'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        # Pydantic's default validation response echoes inputs, which can contain accidental secrets.
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(sqlite3.Error)
    async def storage_unavailable(request: Request, exc: sqlite3.Error):
        log.error("Storage operation failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "Conversation storage is temporarily unavailable. Please try again later."},
        )

    def admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        config = app.state.settings
        supplied = credentials.credentials if credentials else ""
        if not config.admin_token or not secrets.compare_digest(
            supplied.encode(), config.admin_token.encode()
        ):
            raise HTTPException(
                401,
                "Analytics requires a valid server ADMIN_TOKEN. Unlock it in Settings.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def rate_limit(limiter: RateLimiter, request: Request):
        ip = request.client.host if request.client else "unknown"
        retry_after = limiter.check(ip)
        if retry_after:
            raise HTTPException(
                429,
                "Too many requests. Please wait before trying again.",
                headers={"Retry-After": str(retry_after)},
            )

    async def call_provider(question, sources, *, bypass_cooldown=False):
        config = app.state.settings
        status = app.state.provider_status
        cooldown_error = status.cooldown()
        if not bypass_cooldown and cooldown_error:
            raise provider.ProviderError(cooldown_error)
        try:
            try:
                await asyncio.wait_for(app.state.semaphore.acquire(), timeout=config.queue_timeout)
            except TimeoutError as exc:
                raise provider.ProviderError("busy") from exc
            try:
                answer = await provider.generate_answer(
                    config.gemini_key,
                    config.model,
                    question,
                    sources,
                    client=app.state.provider_client,
                    timeout=config.provider_timeout,
                )
            finally:
                app.state.semaphore.release()
            status.success()
            return answer
        except provider.ProviderError as exc:
            status.failure(exc.code)
            log.warning("Provider request failed: category=%s", exc.code)
            raise

    @app.get("/api/health")
    def health():
        config = app.state.settings
        return {
            "status": "ok",
            "version": "1.2.0",
            "provider_configured": bool(config.gemini_key),
            "model": config.model,
            "dataset": "synthetic-demo",
        }

    @app.get("/api/ready")
    def ready():
        app.state.store.ready()
        return {"status": "ready", "database": "ok", "models": "loaded"}

    @app.get("/api/knowledge", response_model=list[FAQ])
    def knowledge():
        return app.state.models.faqs

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest, request: Request):
        rate_limit(app.state.limiter, request)
        start = time.monotonic()
        question = redact(body.message)
        intent, confidence = app.state.models.classify(question)
        sources = app.state.models.retrieve(question)
        mode, notice, provider_error = "retrieval", None, None
        if not sources:
            answer = "I couldn't find that in the sample school knowledge base. Please contact the school for a verified answer. No school contact or handoff service is configured in this demo."
            mode = "no_match"
        else:
            answer = sources[0]["answer"]
            if app.state.settings.gemini_key:
                try:
                    answer = await call_provider(question, sources)
                    mode = "gemini"
                except provider.ProviderError as exc:
                    provider_error = exc.code
                    notice = "Gemini is unavailable. Showing a reference FAQ answer instead."
            else:
                notice = "Gemini is not configured. Showing a reference FAQ answer."
        event_id = str(uuid.uuid4())
        answer = redact(answer)
        elapsed = round((time.monotonic() - start) * 1000)
        await run_in_threadpool(
            app.state.store.save,
            {
                "id": event_id,
                "session_id": str(body.session_id),
                "created_at": datetime.now(UTC).isoformat(),
                "question": question,
                "answer": answer,
                "intent": intent,
                "confidence": confidence,
                "mode": mode,
                "latency_ms": elapsed,
                "source_ids": json.dumps([s["id"] for s in sources]),
                "provider_error": provider_error,
            },
        )
        return {
            "id": event_id,
            "answer": answer,
            "intent": intent,
            "confidence": confidence,
            "mode": mode,
            "latency_ms": elapsed,
            "sources": [{"id": s["id"], "question": s["question"], "score": s["score"]} for s in sources],
            "notice": notice,
            "provider_error": provider_error,
        }

    @app.post("/api/feedback/{event_id}")
    def feedback(event_id: uuid.UUID, body: FeedbackRequest):
        if not app.state.store.feedback(str(event_id), str(body.session_id), body.value):
            raise HTTPException(404, "Message not found in this session")
        return {"ok": True}

    @app.get("/api/analytics", dependencies=[Depends(admin)])
    def analytics():
        return app.state.store.stats()

    @app.get("/api/conversations", dependencies=[Depends(admin)])
    def conversations(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=1_000_000)):
        events = app.state.store.events(limit=limit, offset=offset)
        return {
            "items": [
                {k: v for k, v in event.items() if k not in {"session_id", "source_ids"}} for event in events
            ],
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/evaluation")
    def evaluation():
        return app.state.evaluation

    @app.delete("/api/conversations", dependencies=[Depends(admin)])
    def clear():
        deleted = app.state.store.clear()
        return {"ok": True, "deleted": deleted}

    @app.get("/api/operations", dependencies=[Depends(admin)])
    def operations():
        return operations_snapshot(
            settings=app.state.settings,
            evaluation=app.state.evaluation,
            store=app.state.store,
            provider_status=app.state.provider_status,
            started_at=app.state.started_at,
        )

    @app.get("/api/provider/status", dependencies=[Depends(admin)])
    def provider_status():
        config = app.state.settings
        return app.state.provider_status.snapshot(bool(config.gemini_key), config.model)

    @app.post("/api/provider/check", dependencies=[Depends(admin)])
    async def provider_check(request: Request):
        rate_limit(app.state.check_limiter, request)
        if not app.state.settings.gemini_key:
            return {
                "ok": False,
                "error": "not_configured",
                "message": "No Gemini key is configured on the server.",
            }
        # One minimal generation; no conversation is stored and no user data is sent.
        try:
            reference = app.state.models.faqs[0]
            await call_provider(reference["question"], [reference], bypass_cooldown=True)
            return {"ok": True, **provider_status()}
        except provider.ProviderError as exc:
            return {"ok": False, "error": exc.code, "message": provider.MESSAGES[exc.code]}

    @app.get("/api/export", dependencies=[Depends(admin)])
    def export():
        # Probe availability before streaming response headers. Later infrastructure failures still require monitoring.
        app.state.store.ready()

        def rows():
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
            writer.writeheader()
            yield buffer.getvalue()
            for row in app.state.store.iter_export():
                buffer.seek(0)
                buffer.truncate()
                writer.writerow({k: spreadsheet_safe(v) for k, v in row.items()})
                yield buffer.getvalue()

        return StreamingResponse(
            rows(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="edxso-conversations.csv"'},
        )

    @app.get("/docs", include_in_schema=False)
    def docs():
        return FileResponse(ROOT / "app/static/api-docs.html")

    app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "app/static/index.html")

    return app


app = create_app()
