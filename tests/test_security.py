import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security import (
    RequestSizeLimitMiddleware,
    SameOriginMiddleware,
    SimpleRateLimitMiddleware,
)


def _rate_limited_app(current_time, *, max_requests=2, max_clients=2):
    application = FastAPI()

    @application.get("/limited")
    def limited():
        return {"ok": True}

    application.add_middleware(
        SimpleRateLimitMiddleware,
        max_requests=max_requests,
        window_seconds=10,
        max_clients=max_clients,
        clock=lambda: current_time[0],
    )
    return application


def test_rate_limit_has_retry_after_and_releases_expired_client_buckets():
    current_time = [0.0]
    application = _rate_limited_app(current_time)
    with TestClient(application, client=("198.51.100.1", 50000)) as first_client:
        assert first_client.get("/limited").status_code == 200
        assert first_client.get("/limited").status_code == 200
        limited = first_client.get("/limited")
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == "10"

    with TestClient(application, client=("198.51.100.2", 50000)) as second_client:
        assert second_client.get("/limited").status_code == 200
    with TestClient(application, client=("198.51.100.3", 50000)) as third_client:
        assert third_client.get("/limited").status_code == 429
        current_time[0] = 11
        assert third_client.get("/limited").status_code == 200


def test_rate_limit_does_not_trust_spoofable_forwarded_address():
    current_time = [0.0]
    application = _rate_limited_app(current_time, max_requests=1)
    with TestClient(application, client=("198.51.100.1", 50000)) as client:
        first = client.get("/limited", headers={"x-forwarded-for": "203.0.113.1"})
        second = client.get("/limited", headers={"x-forwarded-for": "203.0.113.2"})
    assert first.status_code == 200
    assert second.status_code == 429


def test_request_size_limit_counts_streamed_chunks_without_content_length():
    received_messages = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"456", "more_body": False},
        ]
    )
    sent_messages = []

    async def receive():
        return next(received_messages)

    async def send(message):
        sent_messages.append(message)

    async def read_body(_scope, app_receive, app_send):
        while True:
            message = await app_receive()
            if not message.get("more_body", False):
                break
        await app_send({"type": "http.response.start", "status": 204, "headers": []})
        await app_send({"type": "http.response.body", "body": b""})

    middleware = RequestSizeLimitMiddleware(read_body, default_max_bytes=5)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/messages",
        "raw_path": b"/api/messages",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("localhost", 80),
    }
    asyncio.run(middleware(scope, receive, send))

    assert sent_messages[0]["status"] == 413
    assert b"Request body is too large" in sent_messages[1]["body"]


def test_voice_upload_path_can_have_a_separate_bounded_limit():
    sent_messages = []
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": b"123456", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        sent_messages.append(message)

    async def read_body(_scope, app_receive, app_send):
        await app_receive()
        await app_send({"type": "http.response.start", "status": 204, "headers": []})
        await app_send({"type": "http.response.body", "body": b""})

    middleware = RequestSizeLimitMiddleware(
        read_body,
        default_max_bytes=4,
        limits_by_path={"/api/voice/transcribe": 8},
    )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/voice/transcribe",
        "raw_path": b"/api/voice/transcribe",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("localhost", 80),
    }
    asyncio.run(middleware(scope, receive, send))
    assert sent_messages[0]["status"] == 204


def test_origin_matching_handles_default_ports_and_rejects_lookalike_hosts():
    matches = SameOriginMiddleware._origin_matches_host
    assert matches("https://demo.trycloudflare.com", "demo.trycloudflare.com")
    assert matches("https://demo.trycloudflare.com", "demo.trycloudflare.com:443")
    assert matches("http://localhost:8000", "localhost:8000")
    assert not matches("https://demo.trycloudflare.com.evil.example", "demo.trycloudflare.com")
    assert not matches("https://demo.trycloudflare.com:444", "demo.trycloudflare.com")
    assert not matches("null", "localhost")
