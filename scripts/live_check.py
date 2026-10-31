"""Opt-in live integration check. Never prints credentials or deletes any records.

Run only when you consent to API usage and synthetic test conversations:
    python -m scripts.live_check --allow-api-usage
"""

import argparse
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-api-usage", action="store_true")
    parser.add_argument("--base-url", default=os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000"))
    args = parser.parse_args()
    if not args.allow_api_usage:
        parser.error(
            "Explicit --allow-api-usage is required; this check invokes Gemini and stores synthetic conversations."
        )
    env = dotenv_values(ROOT / ".env")
    token = os.getenv("TEST_ADMIN_TOKEN") or env.get("ADMIN_TOKEN")
    if not token:
        parser.error("A local ADMIN_TOKEN is required for the diagnostic check")
    auth = {"Authorization": f"Bearer {token}"}
    results = []
    session = str(uuid.uuid4())
    with httpx.Client(base_url=args.base_url, timeout=45) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        readiness = client.get("/api/ready")
        readiness.raise_for_status()
        check = client.post("/api/provider/check", headers=auth)
        check.raise_for_status()
        diagnostic = check.json()
        faqs = client.get("/api/knowledge").json()
        for faq in faqs:
            response = client.post("/api/chat", json={"message": faq["question"], "session_id": session})
            response.raise_for_status()
            result = response.json()
            results.append(
                {
                    "faq_id": faq["id"],
                    "mode": result["mode"],
                    "provider_error": result["provider_error"],
                    "top_source": result["sources"][0]["id"] if result["sources"] else None,
                    "answer": result["answer"],
                    "intent": result["intent"],
                    "latency_ms": result["latency_ms"],
                    "passed": result["mode"] == "gemini"
                    and result["sources"][0]["id"] == faq["id"]
                    and result["intent"] == faq["category"],
                }
            )
        unsupported = client.post("/api/chat", json={"message": "zyxqwv qqqzz", "session_id": session}).json()
        status = client.get("/api/provider/status", headers=auth).json()
        report = {
            "checked_at": datetime.now(UTC).isoformat(),
            "model": health.json()["model"],
            "diagnostic_ok": diagnostic["ok"],
            "readiness_ok": readiness.is_success,
            "faqs": results,
            "unsupported_query_mode": unsupported["mode"],
            "provider_success_count": status["successes"],
            "passed": diagnostic["ok"]
            and all(r["passed"] for r in results)
            and unsupported["mode"] == "no_match",
            "limitations": "Live smoke check, not a comprehensive answer-factuality or prompt-injection evaluation.",
        }
        (ROOT / "artifacts").mkdir(exist_ok=True)
        (ROOT / "artifacts/live-provider-check.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "model": report["model"],
                    "live_diagnostic_ok": diagnostic["ok"],
                    "faq_checks_passed": sum(r["passed"] for r in results),
                    "faq_checks_total": len(results),
                    "unsupported_query_mode": unsupported["mode"],
                    "passed": report["passed"],
                },
                indent=2,
            )
        )
        if not report["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
