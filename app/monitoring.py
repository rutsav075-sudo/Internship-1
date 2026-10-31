"""Read-only operational snapshot. Does not call Gemini or expose conversation text."""

import time

from .config import Settings
from .diagnostics import ProviderStatus
from .store import Store


def operations_snapshot(
    *, settings: Settings, evaluation: dict, store: Store, provider_status: ProviderStatus, started_at: float
) -> dict:
    connected = store.ready()
    stats = store.stats()
    provider = provider_status.snapshot(bool(settings.gemini_key), settings.model)
    warnings = ["School references and model evaluation use synthetic demonstration data."]
    if not provider["configured"]:
        provider_state = "unconfigured"
        warnings.append("Gemini is not configured; supported questions use reference FAQ answers.")
    elif provider["last_error"]:
        provider_state = "error"
        warnings.append(provider["message"])
    elif not provider["last_success_at"]:
        provider_state = "unverified"
        warnings.append("Generation has not been verified since this process started.")
    else:
        provider_state = "verified"
    return {
        "application": {
            "status": "ready",
            "uptime_seconds": max(0, int(time.monotonic() - started_at)),
            "scope": "single-instance-demo",
        },
        "database": {"engine": "SQLite", "connected": connected},
        "model": {
            "algorithm": "TF-IDF + Logistic Regression",
            "serving_samples": evaluation["serving_samples"],
            "dataset_sha256": evaluation["dataset_sha256"],
            "test_samples": evaluation["test_samples"],
            "test_accuracy": evaluation["accuracy"],
            "evaluation_scope": "synthetic-development-test-not-independent-production-validation",
        },
        "traffic": {
            "conversations": stats["total"],
            "sessions": stats["sessions"],
            "answer_modes": stats["modes"],
            "fallback_percent": round(100 * stats["fallback_count"] / stats["total"], 2)
            if stats["total"]
            else None,
            "average_latency_ms": stats["avg_latency_ms"] if stats["total"] else None,
            "p95_latency_ms": stats["p95_latency_ms"],
            "helpful_percent": stats["helpful_percent"],
            "rated_answers": stats["rated"],
        },
        "provider": {"state": provider_state, **provider},
        "warnings": warnings,
        "metric_scope": "Traffic is persisted; provider counters and uptime reset on process restart. No external APM is configured.",
    }
