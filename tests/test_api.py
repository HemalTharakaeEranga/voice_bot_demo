import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    # App startup is exercised without creating or opening the configured user database.
    test_app = create_app(initialize_database=False, default_request_body_limit=256)
    with TestClient(test_app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health", headers={"host": "localhost"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("path", "expected_cache_control"),
    [("/", "no-store"), ("/static/app.js", "no-cache"), ("/static/styles.css", "no-cache")],
)
def test_frontend_entry_files_are_revalidated(client, path, expected_cache_control):
    response = client.get(path, headers={"host": "localhost"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == expected_cache_control


def test_start_session_and_security_headers(client):
    response = client.post(
        "/api/sessions",
        json={"language_locale": "en-US"},
        headers={"host": "localhost"},
    )
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert response.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in response.headers
    assert len(response.json()["session_id"]) == 36


def test_unsupported_language_rejected(client):
    response = client.post(
        "/api/sessions",
        json={"language_locale": "xx-XX"},
        headers={"host": "localhost"},
    )
    assert response.status_code == 422


def test_untrusted_host_is_rejected_with_security_headers(client):
    response = client.post(
        "/api/sessions",
        json={"language_locale": "en-US"},
        headers={"host": "attacker.example"},
    )
    assert response.status_code == 400
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "headers",
    [
        {"host": "localhost", "origin": "https://attacker.example"},
        {"host": "localhost", "sec-fetch-site": "cross-site"},
        {"host": "localhost", "origin": "null"},
    ],
)
def test_cross_origin_api_writes_are_rejected(client, headers):
    response = client.post(
        "/api/sessions",
        json={"language_locale": "en-US"},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-origin request rejected"}
    assert response.headers["cache-control"] == "no-store"


def test_same_origin_and_non_browser_api_clients_are_allowed(client):
    same_origin = client.post(
        "/api/sessions",
        json={"language_locale": "en-US"},
        headers={
            "host": "localhost",
            "origin": "http://localhost",
            "sec-fetch-site": "same-origin",
        },
    )
    command_line = client.post(
        "/api/sessions",
        json={"language_locale": "en-US"},
        headers={"host": "localhost"},
    )
    assert same_origin.status_code == 200
    assert command_line.status_code == 200


def test_oversized_request_is_rejected_before_validation(client):
    response = client.post(
        "/api/sessions",
        content=b"x" * 257,
        headers={"host": "localhost", "content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large"}
    assert response.headers["cache-control"] == "no-store"


def test_unsupported_method_is_explicit_and_not_cached(client):
    response = client.get("/api/sessions", headers={"host": "localhost"})
    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
    assert response.headers["cache-control"] == "no-store"


def test_voice_endpoints_have_a_separate_configurable_rate_limit():
    test_app = create_app(
        initialize_database=False,
        voice_rate_limit_requests=2,
    )
    headers = {"host": "localhost"}
    with TestClient(test_app) as test_client:
        first = test_client.post("/api/voice/speak", json={}, headers=headers)
        second = test_client.post("/api/tts/local", json={}, headers=headers)
        limited = test_client.post("/api/tts/local", json={}, headers=headers)
        booking = test_client.post(
            "/api/sessions",
            json={"language_locale": "en-US"},
            headers=headers,
        )

    assert first.status_code == 422
    assert second.status_code == 422
    assert limited.status_code == 429
    assert limited.json() == {"detail": "Too many requests. Please try again shortly."}
    assert limited.headers["retry-after"] == "60"
    assert limited.headers["cache-control"] == "no-store"
    assert booking.status_code == 200
