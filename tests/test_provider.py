import asyncio
import json

import httpx
import pytest

from app.provider import ProviderError, generate_answer, parse_answer

SOURCES = [{"id": "a", "question": "Question", "answer": "Reference"}]


async def call_with(handler, **kwargs):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await generate_answer(
            "secret", "gemini-3.1-flash-lite", "Question", SOURCES, client=client, **kwargs
        )


async def test_provider_contract():
    def handle(request):
        assert request.headers["x-goog-api-key"] == "secret"
        assert "secret" not in str(request.url)
        assert request.url.path.endswith("/models/gemini-3.1-flash-lite:generateContent")
        payload = json.loads(request.content)
        assert "systemInstruction" in payload
        assert "Reference FAQs" in payload["contents"][0]["parts"][0]["text"]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {"text": "Hidden thought", "thought": True},
                                {"text": "Supported answer"},
                            ]
                        },
                    }
                ]
            },
        )

    assert await call_with(handle) == "Supported answer"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"promptFeedback": "malformed"},
        {"candidates": [{"finishReason": {}}]},
        [],
        None,
        {"candidates": []},
        {"candidates": [None]},
        {"candidates": [{"content": {"parts": []}}]},
        {"candidates": [{"content": []}]},
        {"candidates": [{"content": {"parts": [{"text": None}]}}]},
        {"candidates": [{"content": {"parts": [{"text": "x" * 12001}]}}]},
    ],
)
def test_invalid_provider_payloads(payload):
    with pytest.raises(ProviderError, match="unreadable"):
        parse_answer(payload)


@pytest.mark.parametrize(
    "finish", ["SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "OTHER"]
)
def test_refusal_not_a_success(finish):
    with pytest.raises(ProviderError) as caught:
        parse_answer({"candidates": [{"finishReason": finish, "content": {"parts": [{"text": "Unusable"}]}}]})
    assert caught.value.code == "blocked"


def test_truncation_not_a_success():
    with pytest.raises(ProviderError) as caught:
        parse_answer(
            {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "Partial"}]}}]}
        )
    assert caught.value.code == "truncated"


def test_prompt_block():
    with pytest.raises(ProviderError) as caught:
        parse_answer({"promptFeedback": {"blockReason": "SAFETY"}})
    assert caught.value.code == "blocked"


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "invalid_request"),
        (401, "authentication"),
        (403, "authentication"),
        (404, "model_unavailable"),
        (429, "quota"),
        (500, "upstream"),
        (503, "upstream"),
        (302, "upstream"),
    ],
)
async def test_provider_http_failure(status, code):
    with pytest.raises(ProviderError) as caught:
        await call_with(lambda r: httpx.Response(status, json={"error": {"message": "secret raw error"}}))
    assert caught.value.code == code
    assert "secret raw error" not in str(caught.value)


async def test_invalid_json():
    with pytest.raises(ProviderError) as caught:
        await call_with(lambda r: httpx.Response(200, text="<html>not JSON</html>"))
    assert caught.value.code == "invalid_response"


async def test_http_timeout():
    def fail(request):
        raise httpx.ReadTimeout("secret transport diagnostics")

    with pytest.raises(ProviderError) as caught:
        await call_with(fail)
    assert caught.value.code == "timeout"


async def test_network_failure():
    def fail(request):
        raise httpx.ConnectError("secret diagnostics")

    with pytest.raises(ProviderError) as caught:
        await call_with(fail)
    assert caught.value.code == "network"


async def test_total_deadline():
    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={})

    with pytest.raises(ProviderError) as caught:
        await call_with(slow, timeout=0.01)
    assert caught.value.code == "timeout"


async def test_model_path_rejected():
    with pytest.raises(ProviderError):
        await generate_answer("secret", "../../unsafe", "Question", [])


async def test_owned_client_is_closed(monkeypatch):
    from app import provider

    real_client = httpx.AsyncClient
    made = []

    def make(**kwargs):
        client = real_client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})
            ),
            **kwargs,
        )
        made.append(client)
        return client

    monkeypatch.setattr(provider.httpx, "AsyncClient", make)
    assert await generate_answer("secret", "model", "Question", []) == "OK"
    assert made[0].is_closed


async def test_invalid_api_key_reason():
    with pytest.raises(ProviderError) as caught:
        await call_with(
            lambda r: httpx.Response(400, json={"error": {"details": [{"reason": "API_KEY_INVALID"}]}})
        )
    assert caught.value.code == "authentication"


@pytest.mark.parametrize("body", ["not json", "[]", '{"error": null}'])
async def test_malformed_400_error_is_sanitized(body):
    with pytest.raises(ProviderError) as caught:
        await call_with(lambda request: httpx.Response(400, text=body))
    assert caught.value.code == "invalid_request"
