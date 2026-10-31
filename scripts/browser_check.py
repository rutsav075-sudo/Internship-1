"""Optional integration smoke check against a running local server.
Install: pip install playwright && python -m playwright install chromium
Run: python -m scripts.browser_check
"""

import json
import os
from pathlib import Path

from dotenv import dotenv_values
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")
if __name__ == "__main__":
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    token = dotenv_values(ROOT / ".env").get("ADMIN_TOKEN")
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1120}, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda e: errors.append(e.text) if e.type == "error" else None)
        health = page.request.get(BASE + "/api/health").json()
        expected_mode = os.getenv("TEST_EXPECT_MODE") or (
            "gemini" if health["provider_configured"] else "retrieval"
        )
        if health["provider_configured"] and os.getenv("TEST_ALLOW_API_USAGE") != "true":
            raise SystemExit(
                "Live browser testing requires TEST_ALLOW_API_USAGE=true; use an isolated no-key server for offline tests."
            )
        page.goto(BASE, wait_until="networkidle")
        expect(page.locator("h1:visible")).to_contain_text("A little clarity")
        page.screenshot(path=str(artifacts / "overview-desktop.png"), full_page=True)
        page.locator('nav [href="#assistant"]').click()
        page.locator('[data-prompt="How do I apply for admission?"]').click()
        expect(page.locator(".message.assistant").last).to_contain_text(
            "Gemini answer" if expected_mode == "gemini" else "Reference FAQ", timeout=45000
        )
        page.get_by_role("button", name="Helpful ↑", exact=True).click()
        page.locator("#question").fill('<script>alert("xss")</script> What are the school fees?')
        page.locator("#send-button").click()
        expect(page.locator(".message.assistant").last).to_contain_text(
            "Gemini answer" if expected_mode == "gemini" else "Reference FAQ", timeout=45000
        )
        assert page.locator(".messages script").count() == 0
        page.screenshot(path=str(artifacts / "assistant-desktop.png"), full_page=True)
        page.locator("#handoff-button").click()
        expect(page.locator("#handoff-dialog")).to_be_visible()
        page.locator("#close-dialog").click()
        page.goto(BASE + "/#knowledge")
        page.locator("#knowledge-search").fill("bus")
        expect(page.locator(".knowledge-card")).to_have_count(1)
        page.locator("#knowledge-search").fill("zzzzzz")
        expect(page.locator("#knowledge-list")).to_contain_text("No matching references")
        page.goto(BASE + "/#evaluation")
        expect(page.locator("#evaluation-content")).to_contain_text("Held-out accuracy")
        if token:
            page.goto(BASE + "/#settings")
            page.locator("#admin-token").fill(token)
            page.locator("#unlock-form button").click()
            expect(page.locator("#metric-total")).not_to_have_text("—")
            expect(page.locator("#recent-conversations")).to_contain_text("admission")
            assert page.locator(".bar-fill").count() == 5
            page.screenshot(path=str(artifacts / "analytics-desktop.png"), full_page=True)
            with page.expect_download() as download_info:
                page.locator("#export-button").click()
            assert download_info.value.suggested_filename.endswith(".csv")
            # Destructive checks require explicit opt-in. Use only against an isolated test database.
            if os.getenv("TEST_ALLOW_DELETE") == "true":
                page.goto(BASE + "/#settings")
                page.once("dialog", lambda d: d.accept())
                page.locator("#delete-data").click()
                expect(page.locator("#toast")).to_contain_text("deleted")
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(BASE)
        expect(page.locator("h1:visible")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(artifacts / "overview-mobile.png"), full_page=True)
        page.locator("#menu-toggle").click()
        page.locator('nav [href="#assistant"]').click()
        expect(page.locator(".chat-panel")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(artifacts / "assistant-mobile.png"), full_page=True)
        browser.close()
    (artifacts / "browser-check.json").write_text(
        json.dumps(
            {
                "passed": not errors,
                "console_errors": errors,
                "checks": [
                    "desktop navigation",
                    "FAQ chat",
                    "feedback",
                    "XSS escaping",
                    "handoff dialog",
                    "knowledge search",
                    "model evaluation",
                    "admin unlock",
                    "analytics bars",
                    "CSV download",
                    "admin deletion (only with TEST_ALLOW_DELETE=true)",
                    "mobile navigation",
                    "mobile horizontal overflow",
                ],
            },
            indent=2,
        )
    )
    assert not errors, errors
    print("Browser smoke checks passed; no JavaScript or console errors.")
