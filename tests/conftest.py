"""Default suite is offline, even when the developer has live credentials in .env."""

import httpx
import pytest


@pytest.fixture(autouse=True)
def block_real_provider_network(monkeypatch):
    async def blocked(*args, **kwargs):
        raise AssertionError(
            "Unexpected network request: use an injected MockTransport or the opt-in live-check script"
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)
