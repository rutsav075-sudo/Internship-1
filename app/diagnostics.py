"""Process-local provider health, containing no prompts, answers or credentials."""

import time
from datetime import UTC, datetime

from .provider import MESSAGES


class ProviderStatus:
    def __init__(self):
        self.last_checked_at = None
        self.last_success_at = None
        self.last_error = None
        self.successes = 0
        self.failures = 0
        self.cooldown_until = 0.0

    def success(self):
        self.last_checked_at = datetime.now(UTC).isoformat()
        self.last_success_at = self.last_checked_at
        self.last_error = None
        self.successes += 1
        self.cooldown_until = 0.0

    def failure(self, code):
        self.last_checked_at = datetime.now(UTC).isoformat()
        self.last_error = code
        self.failures += 1
        if code in {"authentication", "model_unavailable", "quota"}:
            self.cooldown_until = time.monotonic() + 60

    def cooldown(self):
        return self.last_error if time.monotonic() < self.cooldown_until else None

    def snapshot(self, configured: bool, model: str):
        return {
            "configured": configured,
            "model": model,
            "last_checked_at": self.last_checked_at,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
            "message": MESSAGES.get(self.last_error),
            "successes": self.successes,
            "failures": self.failures,
            "cooldown_seconds": max(0, round(self.cooldown_until - time.monotonic())),
        }
