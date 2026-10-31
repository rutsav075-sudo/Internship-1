"""Opt-in browser fault injection against a disposable, no-key server.

TEST_BASE_URL=http://127.0.0.1:8001 python -m scripts.browser_resilience
Never run this against a production deployment.
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import dotenv_values
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8001")


async def main():
    token = os.getenv("TEST_ADMIN_TOKEN") or dotenv_values(ROOT / ".env").get("ADMIN_TOKEN")
    checks = []
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        health = await (await page.request.get(BASE + "/api/health")).json()
        if health["provider_configured"]:
            raise SystemExit(
                "Refusing fault-injection checks against a live-key server. Use an isolated no-key server."
            )
        await page.goto(BASE)
        for invalid in ["toString", "__proto__", "constructor", "unknown-page"]:
            await page.goto(BASE + "/#" + invalid)
            await expect(page.locator("#view-overview")).to_be_visible()
        checks.append("unknown/prototype hashes fall back to overview")

        await page.goto(BASE + "/#assistant")

        async def unavailable(route):
            await route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "Storage temporarily unavailable"}),
            )

        await page.route("**/api/chat", unavailable)
        await page.locator("#question").fill("How do I apply for admission?")
        await page.locator("#send-button").click()
        await expect(page.locator(".message.assistant").last).to_contain_text(
            "Storage temporarily unavailable"
        )
        await expect(page.locator("#question")).to_have_value("How do I apply for admission?")
        await expect(page.locator("#send-button")).to_be_enabled()
        await page.unroute("**/api/chat", unavailable)
        checks.append("HTTP 503 keeps question recoverable and re-enables controls")

        async def offline(route):
            await route.abort("internetdisconnected")

        await page.route("**/api/chat", offline)
        await page.locator("#send-button").click()
        await expect(page.locator(".message.assistant").last).to_contain_text("Connection lost")
        await expect(page.locator("#send-button")).to_be_enabled()
        await page.unroute("**/api/chat", offline)
        checks.append("network disconnection has an actionable error")

        requested = asyncio.Event()
        release = asyncio.Event()
        count = [0]

        async def delayed_chat(route):
            count[0] += 1
            requested.set()
            await release.wait()
            await route.continue_()

        await page.route("**/api/chat", delayed_chat)
        await page.locator("#send-button").click()
        await requested.wait()
        await expect(page.locator("#send-button")).to_be_disabled()
        await expect(page.locator("#new-chat")).to_be_disabled()
        await expect(page.locator("#chat-form")).to_have_attribute("aria-busy", "true")
        await page.locator("#question").fill("What are the fees?")
        await page.locator("#question").press("Enter")
        assert count[0] == 1
        release.set()
        await expect(page.locator("#send-button")).to_be_enabled()
        await page.unroute("**/api/chat", delayed_chat)
        checks.append("busy state prevents double-submit and session resets")
        await page.locator("#new-chat").click()
        await expect(page.locator(".message")).to_have_count(1)
        await expect(page.locator("#question")).to_have_value("")
        checks.append("new conversation clears display and composer")

        await page.goto(BASE + "/#knowledge")
        await page.locator("#knowledge-search").fill("<img src=x onerror=alert(1)>")
        await expect(page.locator("#knowledge-list")).to_contain_text("No matching references")
        assert await page.locator("#knowledge-list img").count() == 0
        checks.append("search input is treated as text")

        if token:
            await page.goto(BASE + "/#settings")
            await page.locator("#admin-token").fill(token)
            await page.locator("#unlock-form button").click()
            await expect(page.locator("#metric-total")).not_to_have_text("—")
            await page.goto(BASE + "/#settings")
            await page.locator("#test-provider").click()
            await expect(page.locator("#provider-diagnostics")).to_contain_text("No Gemini key")
            checks.append("no-key live diagnostic reports not configured without fake success")
            await page.locator("#refresh-operations").click()
            await expect(page.locator("#operations-summary")).to_contain_text("SQLite · connected")
            await expect(page.locator("#operations-summary")).to_contain_text("unconfigured")
            checks.append(
                "protected operations dashboard shows database and honest provider state without generation"
            )

            pending = asyncio.Event()
            release_analytics = asyncio.Event()

            async def slow_analytics(route):
                pending.set()
                await release_analytics.wait()
                await route.continue_()

            await page.route("**/api/analytics", slow_analytics)
            await page.goto(BASE + "/#overview")
            await pending.wait()
            await page.goto(BASE + "/#settings")
            await page.locator("#lock-button").click()
            await expect(page.locator("#operations-summary")).to_contain_text("Unlock analytics")
            release_analytics.set()
            await expect(page.locator("#metric-total")).to_have_text("—")
            await page.unroute("**/api/analytics", slow_analytics)
            await page.goto(BASE + "/#overview")
            await expect(page.locator("#recent-conversations")).to_contain_text(
                "Conversation insights stay private"
            )
            checks.append("locking analytics prevents an in-flight response from restoring private data")
            await page.goto(BASE + "/#settings")
            await expect(page.locator("#admin-token")).to_have_value("")
            await page.locator("#test-provider").click()
            await expect(page.locator("#toast")).to_contain_text("Unlock analytics")
            checks.append("locked provider check requires admin access")

        for width in [320, 390, 768, 1024, 1440]:
            await page.set_viewport_size({"width": width, "height": 900})
            for route in ["overview", "assistant", "knowledge", "evaluation", "settings"]:
                await page.goto(BASE + "/#" + route)
                await expect(page.locator("#view-" + route)).to_be_visible()
                assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    width,
                    route,
                )
            if width in [320, 390]:
                await page.locator("#menu-toggle").click()
                await expect(page.locator("#menu-toggle")).to_have_attribute("aria-expanded", "true")
                await page.locator('nav [href="#assistant"]').click()
                await expect(page.locator("#menu-toggle")).to_have_attribute("aria-expanded", "false")
        checks.append(
            "all 5 screens fit widths 320, 390, 768, 1024 and 1440; mobile menu state is accessible"
        )
        await page.goto(BASE + "/docs")
        assert await page.locator("table tbody tr").count() == 13
        checks.append("13 self-contained endpoint descriptions render")
        await browser.close()
    report = {
        "passed": not errors,
        "checks": checks,
        "javascript_errors": errors,
        "note": "Intentional failed HTTP/network calls were injected. They are expected, not successful-provider evidence.",
    }
    (ROOT / "artifacts/browser-resilience.json").write_text(json.dumps(report, indent=2))
    assert not errors, errors
    print(f"{len(checks)} browser resilience checks passed; no uncaught JavaScript errors.")


if __name__ == "__main__":
    asyncio.run(main())
