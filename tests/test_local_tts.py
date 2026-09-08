import hashlib
import sys
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import local_tts


class FakeVoice:
    def __init__(self) -> None:
        self.received_text = ""

    def synthesize_wav(self, text, wav_file) -> None:
        self.received_text = text
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22_050)
        wav_file.writeframes(b"\x00\x00" * 8)


@pytest.mark.parametrize(
    "locale, text",
    [
        ("si-LK", "  ආයුබෝවන්.   ඔබට කොහොමද?  "),
        ("ta-LK", "  வணக்கம்.   எப்படி இருக்கிறீர்கள்?  "),
        ("ar-SA", "  مرحبًا.   كيف حالك؟  "),
    ],
)
def test_generate_local_speech_preserves_unicode_and_returns_wav(monkeypatch, locale, text):
    fake_voice = FakeVoice()
    monkeypatch.setattr(local_tts, "_get_voice", lambda _locale: fake_voice)

    audio = local_tts.generate_local_speech(text, locale)

    assert fake_voice.received_text == " ".join(text.split())
    assert audio.startswith(b"RIFF")
    assert audio[8:12] == b"WAVE"
    with wave.open(BytesIO(audio), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 22_050
        assert wav_file.getnframes() == 8


@pytest.mark.parametrize(
    "text, locale, expected",
    [
        ("   ", "si-LK", "cannot be empty"),
        ("x" * (local_tts.MAX_LOCAL_SPEECH_CHARACTERS + 1), "ta-LK", "at most"),
        ("hello", "en-US", "no configured local voice"),
    ],
)
def test_generate_local_speech_rejects_invalid_input(text, locale, expected):
    with pytest.raises((ValueError, local_tts.LocalVoiceUnavailableError), match=expected):
        local_tts.generate_local_speech(text, locale)


def test_verify_file_accepts_expected_digest_and_rejects_changes(tmp_path):
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"verified model")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()

    local_tts._verify_file(model, digest)
    model.write_bytes(b"modified model")

    with pytest.raises(local_tts.LocalVoiceUnavailableError, match="integrity"):
        local_tts._verify_file(model, digest)
    with pytest.raises(local_tts.LocalVoiceUnavailableError, match="missing"):
        local_tts._verify_file(tmp_path / "missing.onnx", digest)


def test_available_local_voices_rejects_git_lfs_pointer(monkeypatch, tmp_path):
    model = tmp_path / "voice.onnx"
    config = tmp_path / "voice.onnx.json"
    model.write_text("version https://git-lfs.github.com/spec/v1", encoding="utf-8")
    config.write_text("{}", encoding="utf-8")
    files = local_tts.LocalVoiceFiles(
        model_path=model,
        config_path=config,
        model_bytes=63_516_050,
        config_bytes=7_085,
        model_sha256="0" * 64,
        config_sha256="0" * 64,
    )
    monkeypatch.setattr(local_tts, "LOCAL_VOICES", {"si-LK": files})
    monkeypatch.setattr(local_tts, "find_spec", lambda _name: object())

    assert local_tts.available_local_voice_locales() == ()


def test_get_voice_verifies_once_and_reuses_cached_model(monkeypatch):
    loaded_voice = object()
    load_calls = []
    verify_calls = []
    files = local_tts.LocalVoiceFiles(
        model_path=Path("fixed-model.onnx"),
        config_path=Path("fixed-model.onnx.json"),
        model_bytes=10,
        config_bytes=10,
        model_sha256="1" * 64,
        config_sha256="2" * 64,
    )

    class FakePiperVoice:
        @staticmethod
        def load(model_path, *, config_path):
            load_calls.append((model_path, config_path))
            return loaded_voice

    monkeypatch.setattr(local_tts, "LOCAL_VOICES", {"si-LK": files})
    monkeypatch.setattr(
        local_tts,
        "_verify_file",
        lambda path, digest: verify_calls.append((path, digest)),
    )
    monkeypatch.setitem(sys.modules, "piper", SimpleNamespace(PiperVoice=FakePiperVoice))
    local_tts._get_voice.cache_clear()
    try:
        assert local_tts._get_voice("si-LK") is loaded_voice
        assert local_tts._get_voice("si-LK") is loaded_voice
    finally:
        local_tts._get_voice.cache_clear()

    assert verify_calls == [
        (files.model_path, files.model_sha256),
        (files.config_path, files.config_sha256),
    ]
    assert load_calls == [(files.model_path, files.config_path)]


def test_generation_wraps_runtime_details(monkeypatch):
    class BrokenVoice:
        @staticmethod
        def synthesize_wav(_text, _wav_file):
            raise RuntimeError("private inference details")

    monkeypatch.setattr(local_tts, "_get_voice", lambda _locale: BrokenVoice())

    with pytest.raises(local_tts.LocalVoiceGenerationError, match="generation failed") as error:
        local_tts.generate_local_speech("ආයුබෝවන්", "si-LK")
    assert "private" not in str(error.value)


@pytest.mark.parametrize("locale", local_tts.LOCAL_VOICE_LOCALES)
def test_bundled_local_voice_files_have_pinned_integrity(locale):
    files = local_tts.LOCAL_VOICES[locale]

    assert files.model_path.stat().st_size == files.model_bytes
    assert files.config_path.stat().st_size == files.config_bytes
    local_tts._verify_file(files.model_path, files.model_sha256)
    local_tts._verify_file(files.config_path, files.config_sha256)
