"""Server-side OpenAI speech; the booking state machine stays deterministic."""

import unicodedata
from datetime import date, datetime, timedelta, timezone
from threading import BoundedSemaphore
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator

from app.config import Settings, get_settings
from app.dialogue.translations import LANGUAGES
from app.local_tts import (
    LOCAL_VOICE_LOCALES,
    LocalVoiceGenerationError,
    LocalVoiceUnavailableError,
    available_local_voice_locales,
    generate_local_speech,
)

router = APIRouter(prefix="/api", tags=["voice"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_TRANSCRIPT_CHARACTERS = 4096
OPENAI_BASE_URL = "https://api.openai.com/v1"
MAX_CONCURRENT_LOCAL_SPEECH = 2
_LOCAL_SPEECH_ADMISSION = BoundedSemaphore(MAX_CONCURRENT_LOCAL_SPEECH)
AUDIO_FORMATS = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/mp4": "mp4",
    "video/mp4": "mp4",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mpga": "mpga",
}
CONFIRMATION_WORDS = {
    "en-US": ("yes", "no"),
    "si-LK": ("ඔව්", "නැහැ"),
    "ta-LK": ("ஆம்", "இல்லை"),
    "hi-IN": ("हाँ", "नहीं"),
    "es-ES": ("sí", "no"),
    "fr-FR": ("oui", "non"),
    "de-DE": ("ja", "nein"),
    "ar-SA": ("نعم", "لا"),
    "zh-CN": ("是", "否"),
    "ja-JP": ("はい", "いいえ"),
}
LANGUAGE_CODE_TO_LOCALE = {
    "en": "en-US",
    "si": "si-LK",
    "ta": "ta-LK",
    "hi": "hi-IN",
    "es": "es-ES",
    "fr": "fr-FR",
    "de": "de-DE",
    "ar": "ar-SA",
    "zh": "zh-CN",
    "ja": "ja-JP",
}
SPEECH_LANGUAGE_NAMES = {
    "en-US": "English",
    "si-LK": "Sinhala",
    "ta-LK": "Tamil",
    "hi-IN": "Hindi",
    "es-ES": "Spanish",
    "fr-FR": "French",
    "de-DE": "German",
    "ar-SA": "Arabic",
    "zh-CN": "Simplified Chinese Mandarin",
    "ja-JP": "Japanese",
}
LANGUAGE_ALIASES = {
    "eng": "en",
    "english": "en",
    "sin": "si",
    "sinhala": "si",
    "sinhalese": "si",
    "tam": "ta",
    "tamil": "ta",
    "hin": "hi",
    "hindi": "hi",
    "spa": "es",
    "spanish": "es",
    "espanol": "es",
    "fra": "fr",
    "fre": "fr",
    "french": "fr",
    "francais": "fr",
    "deu": "de",
    "ger": "de",
    "german": "de",
    "deutsch": "de",
    "ara": "ar",
    "arabic": "ar",
    "zho": "zh",
    "chi": "zh",
    "cmn": "zh",
    "chinese": "zh",
    "mandarin": "zh",
    "mandarin chinese": "zh",
    "simplified chinese": "zh",
    "jpn": "ja",
    "japanese": "ja",
}


class VoiceLanguage(BaseModel):
    locale: str
    label: str
    greeting: str
    sample: str
    yes: list[str]
    no: list[str]
    openai_experimental: bool


class VoiceModels(BaseModel):
    transcription: str
    speech: str


class VoiceConfig(BaseModel):
    openai_configured: bool
    clinic_today: date
    clinic_utc_offset_minutes: int
    local_voice_locales: list[str]
    languages: list[VoiceLanguage]
    models: VoiceModels


class ConnectionCheck(BaseModel):
    status: Literal["available"] = "available"
    message: str
    models: VoiceModels


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    language_locale: str = Field(default="en-US", max_length=16)

    @field_validator("language_locale")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if value not in LANGUAGES:
            raise ValueError("Unsupported language locale")
        return value

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Speech text cannot be empty")
        return normalized


class TranscriptionResponse(BaseModel):
    text: str
    language_locale: str = Field(max_length=16)
    language_detected: bool
    language_code: str | None = Field(default=None, max_length=2)


def _models(settings: Settings) -> VoiceModels:
    return VoiceModels(
        transcription=settings.openai_transcription_model, speech=settings.openai_speech_model
    )


def _require_key(settings: Settings) -> str:
    if not settings.openai_configured:
        raise HTTPException(
            status_code=503,
            detail="OpenAI is not configured. Add OPENAI_API_KEY to the server .env and restart.",
        )
    return settings.openai_api_key.get_secret_value().strip()


async def _openai_request(
    settings: Settings,
    method: str,
    path: str,
    *,
    data: dict[str, str | list[str]] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    json_body: dict[str, str] | None = None,
) -> httpx.Response:
    key = _require_key(settings)
    try:
        # Fixed host, no redirects and no retries: never send the key elsewhere or
        # silently repeat a potentially billable speech request.
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.openai_timeout_seconds, connect=10),
            follow_redirects=False,
        ) as client:
            response = await client.request(
                method,
                f"{OPENAI_BASE_URL}{path}",
                headers={"Authorization": f"Bearer {key}"},
                data=data,
                files=files,
                json=json_body,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "OpenAI timed out. Please try again.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, "Cannot reach OpenAI. Check the server connection.") from exc

    if response.status_code in {401, 403}:
        raise HTTPException(502, "OpenAI rejected the server API key or its permissions.")
    if response.status_code == 429:
        raise HTTPException(
            429, "OpenAI usage limit reached. Check API billing or try again later."
        )
    if response.status_code == 404:
        raise HTTPException(502, "The configured OpenAI model is unavailable for this API key.")
    if response.status_code in {400, 413, 415, 422}:
        raise HTTPException(
            422, "OpenAI could not process this request. Check the audio or server model settings."
        )
    if response.status_code >= 500:
        raise HTTPException(503, "OpenAI is temporarily unavailable. Please try again later.")
    if not 200 <= response.status_code < 300:
        raise HTTPException(502, "OpenAI returned an unexpected response.")
    return response


def _json_object(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(502, "OpenAI returned an invalid response.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(502, "OpenAI returned an invalid response.")
    return payload


def _normalize_language_identifier(value: str) -> str:
    """Normalize only enough to compare provider metadata with a fixed allowlist."""
    value = value.strip().casefold().replace("_", "-")
    value = " ".join(value.split())
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


def _transcription_language_code(locale: str) -> str:
    """Return an allowlisted provider hint for one configured locale."""
    normalized = locale.casefold()
    # Preserve the documented regional form for Simplified Chinese. The other
    # configured locales use their ISO-639-1 language code.
    return normalized if normalized.startswith("zh-") else normalized.split("-", 1)[0]


def _transcription_form_data(
    settings: Settings, language_locale: str
) -> dict[str, str | list[str]]:
    data: dict[str, str | list[str]] = {
        "model": settings.openai_transcription_model,
        "response_format": "json",
    }
    if settings.openai_transcription_model.startswith("gpt-transcribe"):
        selected_locales = LANGUAGES if language_locale == "auto" else (language_locale,)
        # gpt-transcribe uses the plural field. Constraining automatic mode to
        # the product's fixed allowlist improves recognition while still
        # allowing the provider to report that detection was uncertain.
        data["languages[]"] = [
            _transcription_language_code(locale) for locale in selected_locales
        ]
    elif language_locale != "auto":
        data["language"] = _transcription_language_code(language_locale)
    return data


def _supported_detected_language(payload: dict) -> tuple[str, str] | None:
    """Return a configured locale and canonical ISO code from trusted response fields."""
    candidates: list[object] = []
    languages = payload.get("languages")
    if isinstance(languages, list):
        candidates.extend(languages)
    elif "languages" not in payload:
        # Some older transcription response formats use a singular language
        # field. Never let it override gpt-transcribe's authoritative empty
        # languages array, which means detection was unreliable.
        legacy_language = payload.get("language")
        if isinstance(legacy_language, str):
            candidates.append({"code": legacy_language})

    matches: dict[str, str] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        raw_code = candidate.get("code")
        if not isinstance(raw_code, str) or len(raw_code) > 64:
            continue
        identifier = _normalize_language_identifier(raw_code)
        code = LANGUAGE_ALIASES.get(identifier)
        if code is None:
            parts = identifier.split("-")
            if not 1 <= len(parts) <= 4 or any(
                not part.isascii() or not part.isalnum() or len(part) > 8 for part in parts
            ):
                continue
            code = parts[0]
        locale = LANGUAGE_CODE_TO_LOCALE.get(code)
        if locale in LANGUAGES:
            matches[locale] = code

    # The API does not document languages[] as a ranked list. Switching the
    # booking locale is safe only when all supported matches resolve to one locale.
    if len(matches) != 1:
        return None
    locale, code = next(iter(matches.items()))
    return locale, code


@router.get("/config", response_model=VoiceConfig)
def voice_config(response: Response, settings: SettingsDependency) -> VoiceConfig:
    response.headers["Cache-Control"] = "no-store"
    clinic_timezone = timezone(timedelta(minutes=settings.clinic_utc_offset_minutes))
    return VoiceConfig(
        openai_configured=settings.openai_configured,
        clinic_today=datetime.now(clinic_timezone).date(),
        clinic_utc_offset_minutes=settings.clinic_utc_offset_minutes,
        local_voice_locales=list(available_local_voice_locales()),
        languages=[
            VoiceLanguage(
                locale=language.locale,
                label=language.label,
                greeting=language.prompts["greeting"],
                sample=language.prompts["ask_name"],
                yes=[CONFIRMATION_WORDS[language.locale][0]],
                no=[CONFIRMATION_WORDS[language.locale][1]],
                openai_experimental=language.locale == "si-LK",
            )
            for language in LANGUAGES.values()
        ],
        models=_models(settings),
    )


@router.post("/voice/check", response_model=ConnectionCheck)
async def check_connection(response: Response, settings: SettingsDependency) -> ConnectionCheck:
    response.headers["Cache-Control"] = "no-store"
    models = _models(settings)
    for model in {models.transcription, models.speech}:
        upstream = await _openai_request(settings, "GET", f"/models/{model}")
        if _json_object(upstream).get("id") != model:
            raise HTTPException(502, "OpenAI returned an unexpected model response.")
    return ConnectionCheck(
        message=(
            "API key and model visibility checked. "
            "Record and play a sample to test speech and available quota."
        ),
        models=models,
    )


def _valid_audio_header(content: bytes, extension: str) -> bool:
    """Reject obvious non-audio uploads; the provider performs full decoding."""
    if extension == "webm":
        return content.startswith(b"\x1a\x45\xdf\xa3")
    if extension in {"mp4", "m4a"}:
        return len(content) >= 12 and content[4:8] == b"ftyp"
    if extension == "wav":
        return content.startswith(b"RIFF") and content[8:12] == b"WAVE"
    return content.startswith(b"ID3") or (
        len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
    )


@router.post(
    "/voice/transcribe",
    response_model=TranscriptionResponse,
    response_model_exclude_none=True,
)
async def transcribe(
    response: Response,
    settings: SettingsDependency,
    audio: Annotated[UploadFile, File()],
    language_locale: Annotated[str, Form(max_length=16)] = "en-US",
    fallback_locale: Annotated[str, Form(max_length=16)] = "en-US",
) -> TranscriptionResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        if language_locale != "auto" and language_locale not in LANGUAGES:
            raise HTTPException(422, "Unsupported language locale")
        if fallback_locale not in LANGUAGES:
            raise HTTPException(422, "Unsupported fallback language locale")
        _require_key(settings)
        content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
        extension = AUDIO_FORMATS.get(content_type)
        if extension is None:
            raise HTTPException(415, "Use a WebM, MP4, M4A, WAV or MP3 recording.")
        content = await audio.read(MAX_AUDIO_BYTES + 1)
        if not content:
            raise HTTPException(422, "The recording is empty. Record a short phrase and try again.")
        if len(content) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "The recording exceeds the 10 MB demo limit.")
        if not _valid_audio_header(content, extension):
            raise HTTPException(422, "The recording is not valid audio. Please record again.")
    finally:
        await audio.close()

    data = _transcription_form_data(settings, language_locale)
    upstream = await _openai_request(
        settings,
        "POST",
        "/audio/transcriptions",
        data=data,
        files={"file": (f"recording.{extension}", content, content_type)},
    )
    payload = _json_object(upstream)
    text = payload.get("text")
    if not isinstance(text, str):
        raise HTTPException(502, "OpenAI returned an invalid transcript.")
    text = " ".join(text.split())
    if not text:
        raise HTTPException(422, "No speech was detected. Speak clearly and try again.")
    if len(text) > MAX_TRANSCRIPT_CHARACTERS:
        raise HTTPException(422, "The transcript is too long. Please record a shorter phrase.")
    detected = _supported_detected_language(payload)
    if language_locale != "auto":
        if detected is not None and detected[0] == language_locale:
            return TranscriptionResponse(
                text=text,
                language_locale=language_locale,
                language_detected=True,
                language_code=detected[1],
            )
        return TranscriptionResponse(
            text=text,
            language_locale=language_locale,
            language_detected=False,
        )
    if detected is None:
        return TranscriptionResponse(
            text=text,
            language_locale=fallback_locale,
            language_detected=False,
        )
    detected_locale, detected_code = detected
    return TranscriptionResponse(
        text=text,
        language_locale=detected_locale,
        language_detected=True,
        language_code=detected_code,
    )


@router.post("/voice/speak")
async def speak(request: SpeechRequest, settings: SettingsDependency) -> Response:
    if request.language_locale in LOCAL_VOICE_LOCALES:
        if not _LOCAL_SPEECH_ADMISSION.acquire(blocking=False):
            raise HTTPException(
                429,
                "Local speech is busy. Please try again shortly.",
                headers={"Retry-After": "1"},
            )
        try:
            try:
                audio = await run_in_threadpool(
                    generate_local_speech,
                    request.text,
                    request.language_locale,
                )
            except ValueError as exc:
                raise HTTPException(422, "Local speech text is invalid.") from exc
            except LocalVoiceUnavailableError as exc:
                language = SPEECH_LANGUAGE_NAMES[request.language_locale]
                raise HTTPException(
                    503,
                    f"The local {language} voice is unavailable. Check the server voice files.",
                ) from exc
            except LocalVoiceGenerationError as exc:
                raise HTTPException(
                    503, "Local speech generation failed. Please try again."
                ) from exc
        finally:
            _LOCAL_SPEECH_ADMISSION.release()
        return Response(
            content=audio,
            media_type="audio/wav",
            headers={"Cache-Control": "no-store"},
        )

    payload = {
        "model": settings.openai_speech_model,
        "voice": settings.openai_speech_voice,
        "input": request.text,
        "response_format": "mp3",
    }
    if settings.openai_speech_model.startswith("gpt-4o-mini-tts"):
        payload["instructions"] = (
            f"Use fluent, natural {SPEECH_LANGUAGE_NAMES[request.language_locale]} "
            f"pronunciation ({request.language_locale}) in a warm, professional clinic "
            "receptionist tone. Read the supplied Unicode text exactly. Do not translate, "
            "transliterate, or add words."
        )
    upstream = await _openai_request(settings, "POST", "/audio/speech", json_body=payload)
    if not upstream.content or not upstream.headers.get("content-type", "").startswith("audio/"):
        raise HTTPException(502, "OpenAI returned no playable audio.")
    return Response(
        content=upstream.content, media_type="audio/mpeg", headers={"Cache-Control": "no-store"}
    )
