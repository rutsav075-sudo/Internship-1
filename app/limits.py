"""Bounded single-process rate limiting and ASGI request-size protection."""

import json
import math
import threading
import time
from collections import OrderedDict, deque


class RateLimiter:
    """Monotonic-clock sliding window. Evicts old clients; never trusts proxy headers."""

    def __init__(self, capacity: int, window: float = 60, max_clients: int = 10_000, clock=time.monotonic):
        self.capacity = capacity
        self.window = window
        self.max_clients = max_clients
        self.clock = clock
        self.clients: OrderedDict[str, deque[float]] = OrderedDict()
        self.lock = threading.Lock()

    def check(self, client: str) -> int:
        """Return zero if accepted, otherwise seconds until the oldest event expires."""
        with self.lock:
            now = self.clock()
            while self.clients:
                first = next(iter(self.clients))
                if now - self.clients[first][-1] < self.window:
                    break
                self.clients.popitem(last=False)
            recent = self.clients.setdefault(client, deque())
            while recent and now - recent[0] >= self.window:
                recent.popleft()
            self.clients.move_to_end(client)
            if len(recent) >= self.capacity:
                return max(1, math.ceil(self.window - (now - recent[0])))
            recent.append(now)
            while len(self.clients) > self.max_clients:
                self.clients.popitem(last=False)
            return 0


class RequestSizeLimit:
    """Enforce both declared and actual body sizes, before JSON parsing.

    Buffers at most `maximum` bytes; this API does not accept file uploads.
    """

    def __init__(self, app, maximum=16_384):
        self.app = app
        self.maximum = maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)

        async def reject():
            body = json.dumps({"detail": "Request body is too large"}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")],
                }
            )
            await send({"type": "http.response.body", "body": body})

        headers = dict(scope.get("headers", []))
        try:
            if int(headers.get(b"content-length", b"0")) > self.maximum:
                return await reject()
        except ValueError:
            pass  # The actual byte count below remains authoritative.
        chunks = []
        size = 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            size += len(event.get("body", b""))
            if size > self.maximum:
                return await reject()
            chunks.append(event.get("body", b""))
            if not event.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
