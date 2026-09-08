"""Offline Piper speech for the locally bundled clinic languages."""

import wave
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from importlib.util import find_spec
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any

MAX_LOCAL_SPEECH_CHARACTERS = 1000
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LocalVoiceError(RuntimeError):
    """Base error for safe local voice failures."""


class LocalVoiceUnavailableError(LocalVoiceError):
    """Raised when a required runtime or verified voice file is unavailable."""


class LocalVoiceGenerationError(LocalVoiceError):
    """Raised when Piper cannot produce a valid WAV response."""


@dataclass(frozen=True)
class LocalVoiceFiles:
    model_path: Path
    config_path: Path
    model_bytes: int
    config_bytes: int
    model_sha256: str
    config_sha256: str


LOCAL_VOICES = {
    "si-LK": LocalVoiceFiles(
        model_path=PROJECT_ROOT / "models" / "sinhala" / "si_LK-ashoka-medium.onnx",
        config_path=PROJECT_ROOT
        / "models"
        / "sinhala"
        / "si_LK-ashoka-medium.onnx.json",
        model_bytes=63_516_050,
        config_bytes=7_085,
        model_sha256="7ad3e2fae1c8abbb389abb2cc7b17624b620082193e88407791ae68b9011a166",
        config_sha256="ff7910b0816934384fe5d7342b64a84596837fba513547062dada08844b2c184",
    ),
    "ta-LK": LocalVoiceFiles(
        model_path=PROJECT_ROOT / "models" / "tamil" / "ta_IN-rasa_female-medium.onnx",
        config_path=PROJECT_ROOT
        / "models"
        / "tamil"
        / "ta_IN-rasa_female-medium.onnx.json",
        model_bytes=63_511_037,
        config_bytes=7_091,
        model_sha256="1befd7c4034429cecf3143d5eab4810b29833420aedb951bef4092779d074d59",
        config_sha256="e49a5f947bfe64bc232d9f900a163b3b771b812780fd8efe0d411a3d8f4b4ee2",
    ),
    "ar-SA": LocalVoiceFiles(
        model_path=PROJECT_ROOT / "models" / "arabic" / "ar_JO-kareem-medium.onnx",
        config_path=PROJECT_ROOT
        / "models"
        / "arabic"
        / "ar_JO-kareem-medium.onnx.json",
        model_bytes=63_201_294,
        config_bytes=5_024,
        model_sha256="9e95cab07b679da603bba17c4dec7ab3111320571964ee95c0379603c086491e",
        config_sha256="ea6d9b9d9076dbdb6bf5c98c6a141ef154959d2359709b37855727964e7d6c4d",
    ),
}
LOCAL_VOICE_LOCALES = frozenset(LOCAL_VOICES)
_VOICE_LOCKS = {locale: Lock() for locale in LOCAL_VOICE_LOCALES}


def _has_expected_size(path: Path, expected_bytes: int) -> bool:
    try:
        return path.is_file() and path.stat().st_size == expected_bytes
    except OSError:
        return False


def available_local_voice_locales() -> tuple[str, ...]:
    """Report local routes only when Piper and full model files are present."""
    if find_spec("piper") is None:
        return ()
    return tuple(
        locale
        for locale, files in LOCAL_VOICES.items()
        if _has_expected_size(files.model_path, files.model_bytes)
        and _has_expected_size(files.config_path, files.config_bytes)
    )


def _verify_file(path: Path, expected_digest: str) -> None:
    if not path.is_file():
        raise LocalVoiceUnavailableError("A required local voice file is missing.")
    digest = sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LocalVoiceUnavailableError("A local voice file could not be read.") from exc
    if digest.hexdigest() != expected_digest:
        raise LocalVoiceUnavailableError("A local voice file failed its integrity check.")


@lru_cache(maxsize=len(LOCAL_VOICES))
def _get_voice(language_locale: str) -> Any:
    files = LOCAL_VOICES.get(language_locale)
    if files is None:
        raise LocalVoiceUnavailableError("This language has no configured local voice.")
    _verify_file(files.model_path, files.model_sha256)
    _verify_file(files.config_path, files.config_sha256)
    try:
        from piper import PiperVoice
    except ImportError as exc:
        raise LocalVoiceUnavailableError("The local voice runtime is not installed.") from exc
    try:
        return PiperVoice.load(files.model_path, config_path=files.config_path)
    except Exception as exc:
        raise LocalVoiceUnavailableError("The local voice model could not be loaded.") from exc


def generate_local_speech(text: str, language_locale: str) -> bytes:
    """Generate one bounded WAV response while reusing a verified cached model."""
    clean_text = " ".join(text.split())
    if not clean_text:
        raise ValueError("Speech text cannot be empty.")
    if len(clean_text) > MAX_LOCAL_SPEECH_CHARACTERS:
        raise ValueError(
            f"Local speech text must be at most {MAX_LOCAL_SPEECH_CHARACTERS} characters."
        )
    lock = _VOICE_LOCKS.get(language_locale)
    if lock is None:
        raise LocalVoiceUnavailableError("This language has no configured local voice.")

    try:
        with lock:
            voice = _get_voice(language_locale)
            output = BytesIO()
            with wave.open(output, "wb") as wav_file:
                voice.synthesize_wav(clean_text, wav_file)
            audio = output.getvalue()
    except LocalVoiceError:
        raise
    except Exception as exc:
        raise LocalVoiceGenerationError("Local speech generation failed.") from exc

    if len(audio) <= 44 or not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
        raise LocalVoiceGenerationError("Local speech generation returned invalid audio.")
    return audio
