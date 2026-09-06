import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import voice
from app.config import Settings, get_settings
from app.dialogue.translations import LANGUAGES

DEMO_KEY = "test-only-never-a-real-key"
WEBM_AUDIO = b"\x1a\x45\xdf\xa3" + b"demo audio bytes"


@pytest.fixture
def voice_client(monkeypatch):
    # This isolated app never opens the appointment database or spends API quota.
    settings = Settings(_env_file=None, openai_api_key=DEMO_KEY)
    app = FastAPI()
    app.include_router(voice.router)
    app.dependency_overrides[get_settings] = lambda: settings
    requests = []
    replies = []

    def handle(request):
        requests.append(request)
        assert request.url.host == "api.openai.com"
        assert request.headers["authorization"] == f"Bearer {DEMO_KEY}"
        assert replies, "Unexpected provider request"
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    original_client = httpx.AsyncClient

    def mock_client(**kwargs):
        assert kwargs["follow_redirects"] is False
        return original_client(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(voice.httpx, "AsyncClient", mock_client)
    with TestClient(app) as client:
        yield client, settings, requests, replies


def test_public_config_exposes_ten_languages_but_no_key(voice_client):
    client, _, requests, _ = voice_client
    response = client.get("/api/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["openai_configured"] is True
    assert payload["models"]["transcription"] == "gpt-transcribe"
    assert set(voice.LANGUAGE_CODE_TO_LOCALE.values()) == set(LANGUAGES)
    assert {language["locale"] for language in payload["languages"]} == set(LANGUAGES)
    assert len(payload["languages"]) == 10
    assert all(language["sample"] and language["yes"] for language in payload["languages"])
    for language in payload["languages"]:
        yes, no = voice.CONFIRMATION_WORDS[language["locale"]]
        assert language["yes"] == [yes]
        assert language["no"] == [no]
        assert yes in LANGUAGES[language["locale"]].yes_words
        assert no in LANGUAGES[language["locale"]].no_words
    assert DEMO_KEY not in response.text
    assert "api_key" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert not requests


def test_missing_key_leaves_browser_metadata_available(voice_client):
    client, settings, requests, _ = voice_client
    settings.openai_api_key = type(settings.openai_api_key)("")
    assert client.get("/api/config").json()["openai_configured"] is False
    assert client.post("/api/voice/check").status_code == 503
    assert client.post("/api/voice/speak", json={"text": "Hello"}).status_code == 503
    assert not requests


def test_connection_check_only_reads_model_metadata(voice_client):
    client, settings, requests, replies = voice_client
    for model in {settings.openai_transcription_model, settings.openai_speech_model}:
        replies.append(httpx.Response(200, json={"id": model}))
    response = client.post("/api/voice/check")
    assert response.status_code == 200
    assert response.json()["status"] == "available"
    assert "model visibility" in response.json()["message"]
    assert len(requests) == 2
    assert all(request.method == "GET" and "/models/" in request.url.path for request in requests)


@pytest.mark.parametrize("locale", LANGUAGES)
def test_explicit_transcription_preserves_language_hint_and_uses_safe_filename(
    voice_client, locale
):
    client, _, requests, replies = voice_client
    phrase = LANGUAGES[locale].prompts["ask_name"]
    replies.append(httpx.Response(200, json={"text": f"  {phrase}  "}))
    response = client.post(
        "/api/voice/transcribe",
        data={"language_locale": locale},
        files={"audio": ("../../private-key.txt", WEBM_AUDIO, "audio/webm;codecs=opus")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "text": phrase,
        "language_locale": locale,
        "language_detected": False,
    }
    request = requests[0]
    assert request.url.path == "/v1/audio/transcriptions"
    assert b'filename="recording.webm"' in request.content
    assert b"private-key" not in request.content
    assert b'name="response_format"\r\n\r\njson' in request.content
    language = locale.split("-")[0].encode()
    assert b'name="language"\r\n\r\n' + language in request.content


@pytest.mark.parametrize(
    ("provider_identifier", "locale", "code"),
    [
        ("EN_us", "en-US", "en"),
        ("Sinhalese", "si-LK", "si"),
        ("ta-LK", "ta-LK", "ta"),
        ("Hindi", "hi-IN", "hi"),
        ("Espa\u00f1ol", "es-ES", "es"),
        ("Fran\u00e7ais", "fr-FR", "fr"),
        ("Deutsch", "de-DE", "de"),
        ("Arabic", "ar-SA", "ar"),
        ("Mandarin Chinese", "zh-CN", "zh"),
        ("Japanese", "ja-JP", "ja"),
    ],
)
def test_auto_transcription_maps_each_supported_language(
    voice_client, provider_identifier, locale, code
):
    client, _, requests, replies = voice_client
    replies.append(
        httpx.Response(
            200,
            json={"text": "recognized phrase", "languages": [{"code": provider_identifier}]},
        )
    )
    response = client.post(
        "/api/voice/transcribe",
        data={"language_locale": "auto", "fallback_locale": "de-DE"},
        files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "recognized phrase",
        "language_locale": locale,
        "language_detected": True,
        "language_code": code,
    }
    assert b'name="model"\r\n\r\ngpt-transcribe' in requests[0].content
    assert b'name="language"' not in requests[0].content
    assert b'name="languages"' not in requests[0].content


@pytest.mark.parametrize(
    "languages",
    [
        [],
        [{"code": "ru"}],
        [{"code": "en"}, {"code": "fr"}],
        [{"name": "en"}],
        ["en"],
        [{"code": None}],
        [{"code": "en-<script>"}],
        "en",
    ],
)
def test_unreliable_or_unsupported_detection_uses_declared_fallback(voice_client, languages):
    client, _, _, replies = voice_client
    replies.append(httpx.Response(200, json={"text": "hello", "languages": languages}))
    response = client.post(
        "/api/voice/transcribe",
        data={"language_locale": "auto", "fallback_locale": "ta-LK"},
        files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "hello",
        "language_locale": "ta-LK",
        "language_detected": False,
    }


def test_duplicate_detection_aliases_for_one_locale_are_reliable(voice_client):
    client, _, _, replies = voice_client
    replies.append(
        httpx.Response(
            200,
            json={
                "text": "hola",
                "languages": [{"code": "es"}, {"code": "Spanish"}, {"code": "es-ES"}],
            },
        )
    )
    response = client.post(
        "/api/voice/transcribe",
        data={"language_locale": "auto", "fallback_locale": "en-US"},
        files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")},
    )

    assert response.json()["language_locale"] == "es-ES"
    assert response.json()["language_detected"] is True
    assert response.json()["language_code"] == "es"


def test_legacy_singular_language_metadata_is_allowlisted(voice_client):
    client, _, _, replies = voice_client
    replies.append(httpx.Response(200, json={"text": "bonjour", "language": "French"}))
    response = client.post(
        "/api/voice/transcribe",
        data={"language_locale": "auto"},
        files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")},
    )

    assert response.json()["language_locale"] == "fr-FR"
    assert response.json()["language_detected"] is True
    assert response.json()["language_code"] == "fr"


def test_empty_official_language_list_overrides_legacy_metadata(voice_client):
    client, _, _, replies = voice_client
    replies.append(
        httpx.Response(200, json={"text": "hello", "languages": [], "language": "English"})
    )
    response = client.post(
        "/api/voice/transcribe",
        data={"language_locale": "auto", "fallback_locale": "hi-IN"},
        files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")},
    )

    assert response.json() == {
        "text": "hello",
        "language_locale": "hi-IN",
        "language_detected": False,
    }


def test_model_without_detection_metadata_does_not_claim_detection(voice_client):
    client, settings, requests, replies = voice_client
    settings.openai_transcription_model = "gpt-4o-mini-transcribe"
    replies.append(httpx.Response(200, json={"text": "hello"}))
    response = client.post(
        "/api/voice/transcribe",
        data={"language_locale": "auto", "fallback_locale": "ja-JP"},
        files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")},
    )

    assert response.json() == {
        "text": "hello",
        "language_locale": "ja-JP",
        "language_detected": False,
    }
    assert b"gpt-4o-mini-transcribe" in requests[0].content


def test_explicit_locale_never_switches_on_different_provider_metadata(voice_client):
    client, _, _, replies = voice_client
    replies.append(
        httpx.Response(200, json={"text": "a short name", "languages": [{"code": "en"}]})
    )
    response = client.post(
        "/api/voice/transcribe",
        data={"language_locale": "fr-FR", "fallback_locale": "ja-JP"},
        files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")},
    )

    assert response.json() == {
        "text": "a short name",
        "language_locale": "fr-FR",
        "language_detected": False,
    }


def test_explicit_locale_can_confirm_matching_provider_metadata(voice_client):
    client, _, _, replies = voice_client
    replies.append(
        httpx.Response(200, json={"text": "bonjour", "languages": [{"code": "French"}]})
    )
    response = client.post(
        "/api/voice/transcribe",
        data={"language_locale": "fr-FR"},
        files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")},
    )

    assert response.json() == {
        "text": "bonjour",
        "language_locale": "fr-FR",
        "language_detected": True,
        "language_code": "fr",
    }


@pytest.mark.parametrize(
    "form_data",
    [
        {"language_locale": "xx-XX"},
        {"language_locale": "AUTO"},
        {"language_locale": "auto", "fallback_locale": "xx-XX"},
    ],
)
def test_invalid_transcription_language_input_never_reaches_provider(voice_client, form_data):
    client, _, requests, _ = voice_client
    response = client.post(
        "/api/voice/transcribe",
        data=form_data,
        files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")},
    )
    assert response.status_code == 422
    assert not requests


@pytest.mark.parametrize(
    ("content", "content_type", "status"),
    [
        (b"", "audio/webm", 422),
        (b"plain text", "audio/webm", 422),
        (WEBM_AUDIO, "application/octet-stream", 415),
        (WEBM_AUDIO, "audio/ogg", 415),
    ],
)
def test_invalid_recording_never_reaches_provider(voice_client, content, content_type, status):
    client, _, requests, _ = voice_client
    response = client.post(
        "/api/voice/transcribe", files={"audio": ("sample.webm", content, content_type)}
    )
    assert response.status_code == status
    assert not requests


def test_oversized_recording_never_reaches_provider(voice_client, monkeypatch):
    client, _, requests, _ = voice_client
    monkeypatch.setattr(voice, "MAX_AUDIO_BYTES", 10)
    response = client.post(
        "/api/voice/transcribe", files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")}
    )
    assert response.status_code == 413
    assert not requests


@pytest.mark.parametrize("payload", [{}, {"text": None}, {"text": []}, {"text": "   "}])
def test_missing_or_empty_provider_transcript_is_handled(voice_client, payload):
    client, _, _, replies = voice_client
    replies.append(httpx.Response(200, json=payload))
    response = client.post(
        "/api/voice/transcribe", files={"audio": ("sample.webm", WEBM_AUDIO, "audio/webm")}
    )
    assert response.status_code in {422, 502}


@pytest.mark.parametrize("locale", LANGUAGES)
def test_speech_returns_uncached_audio_for_all_configured_locales(voice_client, locale):
    client, _, requests, replies = voice_client
    replies.append(httpx.Response(200, content=b"ID3demo", headers={"content-type": "audio/mpeg"}))
    text = LANGUAGES[locale].prompts["ask_name"]
    response = client.post("/api/voice/speak", json={"text": text, "language_locale": locale})
    assert response.status_code == 200
    assert response.content == b"ID3demo"
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["cache-control"] == "no-store"
    payload = json.loads(requests[0].content)
    assert payload["input"] == text
    assert locale in payload["instructions"]
    assert payload["response_format"] == "mp3"


@pytest.mark.parametrize(
    "payload",
    [
        {"text": ""},
        {"text": "   "},
        {"text": "x" * 4097},
        {"text": "Hello", "language_locale": "xx-XX"},
    ],
)
def test_invalid_speech_input_never_reaches_provider(voice_client, payload):
    client, _, requests, _ = voice_client
    assert client.post("/api/voice/speak", json=payload).status_code == 422
    assert not requests


@pytest.mark.parametrize(
    "provider_status, expected",
    [(401, 502), (403, 502), (429, 429), (404, 502), (400, 422), (500, 503)],
)
def test_provider_errors_are_safe_and_never_retried(voice_client, provider_status, expected):
    client, _, requests, replies = voice_client
    replies.append(httpx.Response(provider_status, json={"error": {"message": DEMO_KEY}}))
    response = client.post("/api/voice/speak", json={"text": "Hello"})
    assert response.status_code == expected
    assert DEMO_KEY not in response.text
    assert len(requests) == 1


@pytest.mark.parametrize(
    "error, expected",
    [(httpx.ReadTimeout("private details"), 504), (httpx.ConnectError("private details"), 503)],
)
def test_network_failures_are_safe(voice_client, error, expected):
    client, _, requests, replies = voice_client
    replies.append(error)
    response = client.post("/api/voice/speak", json={"text": "Hello"})
    assert response.status_code == expected
    assert "private details" not in response.text
    assert len(requests) == 1


def test_malformed_model_reply_is_not_reported_as_connected(voice_client):
    client, _, _, replies = voice_client
    replies.append(httpx.Response(200, text="not json"))
    assert client.post("/api/voice/check").status_code == 502


def test_non_audio_speech_reply_is_rejected(voice_client):
    client, _, _, replies = voice_client
    replies.append(httpx.Response(200, json={"text": "unexpected"}))
    assert client.post("/api/voice/speak", json={"text": "Hello"}).status_code == 502
