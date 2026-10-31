from app.limits import RateLimiter, RequestSizeLimit


async def run_body(events, *, method="POST", headers=()):
    called = []
    sent = []
    iterator = iter(events)

    async def receive():
        return next(iterator)

    async def send(event):
        sent.append(event)

    async def app(scope, receive, send):
        called.append(True)
        event = await receive()
        sent.append(event)
        if event.get("body") == b"ping":
            sent.append(await receive())

    await RequestSizeLimit(app, maximum=10)(
        {"type": "http", "method": method, "headers": headers}, receive, send
    )
    return called, sent


async def test_chunked_asgi_bytes_are_limited():
    called, sent = await run_body(
        [
            {"type": "http.request", "body": b"a" * 7, "more_body": True},
            {"type": "http.request", "body": b"b" * 7, "more_body": False},
        ]
    )
    assert not called and sent[0]["status"] == 413


async def test_invalid_declared_length_does_not_skip_actual_limit():
    called, sent = await run_body(
        [{"type": "http.request", "body": b"a" * 11}], headers=[(b"content-length", b"bad")]
    )
    assert not called and sent[0]["status"] == 413


async def test_disconnect_before_body_finishes():
    called, sent = await run_body([{"type": "http.disconnect"}])
    assert not called and sent == []


async def test_body_replay_and_disconnect_forwarding():
    called, sent = await run_body(
        [
            {"type": "http.request", "body": b"pi", "more_body": True},
            {"type": "http.request", "body": b"ng", "more_body": False},
            {"type": "http.disconnect"},
        ]
    )
    assert called and sent[0]["body"] == b"ping" and sent[1]["type"] == "http.disconnect"


async def test_get_bypasses_buffer():
    called, sent = await run_body([{"type": "http.request", "body": b"a" * 20}], method="GET")
    assert called and sent[0]["body"] == b"a" * 20


def test_limiter_expires_per_client_events():
    clock = [0.0]
    limiter = RateLimiter(2, clock=lambda: clock[0])
    limiter.check("a")
    clock[0] = 30
    limiter.check("a")
    clock[0] = 61
    # First event expired, second remains; this exercises trimming rather than whole-client eviction.
    assert limiter.check("a") == 0
    assert limiter.check("a") == 29
