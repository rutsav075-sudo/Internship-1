"""Validated configuration; secrets never appear in reprs or API responses."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gemini-3.1-flash-lite"


@dataclass(frozen=True, slots=True)
class Settings:
    gemini_key: str = field(default="", repr=False)
    admin_token: str = field(default="", repr=False)
    model: str = DEFAULT_MODEL
    database_path: str = str(ROOT / "data/app.sqlite3")
    provider_timeout: float = 30.0
    provider_concurrency: int = 8
    queue_timeout: float = 3.0
    chat_rate_limit: int = 20
    max_request_bytes: int = 16_384

    def __post_init__(self):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", self.model):
            raise ValueError("GEMINI_MODEL must be a bare model ID, not a URL or path")
        if self.provider_timeout <= 0 or self.queue_timeout <= 0:
            raise ValueError("Timeouts must be positive")
        if self.provider_concurrency < 1 or self.chat_rate_limit < 1 or self.max_request_bytes < 1:
            raise ValueError("Capacity limits must be positive")
        if not self.database_path.strip():
            raise ValueError("DATABASE_PATH must not be empty")

    @classmethod
    def from_env(cls):
        return cls(
            gemini_key=os.getenv("GEMINI_API_KEY", "").strip(),
            admin_token=os.getenv("ADMIN_TOKEN", "").strip(),
            model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip(),
            database_path=os.getenv("DATABASE_PATH") or str(ROOT / "data/app.sqlite3"),
            provider_timeout=float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "30")),
            provider_concurrency=int(os.getenv("PROVIDER_CONCURRENCY", "8")),
            chat_rate_limit=int(os.getenv("CHAT_RATE_LIMIT", "20")),
        )
