from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "production"] = "development"
    database_url: str = "sqlite:///./voicebot_demo.db"
    allowed_hosts: str = "localhost,127.0.0.1"
    rate_limit_requests: int = Field(default=60, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    voice_rate_limit_requests: int = Field(default=30, ge=1, le=1000)
    clinic_utc_offset_minutes: int = Field(default=330, ge=-720, le=840)
    openai_api_key: SecretStr = SecretStr("")
    openai_transcription_model: str = Field(
        default="gpt-transcribe", pattern=r"^[A-Za-z0-9._-]{1,100}$"
    )
    openai_speech_model: str = Field(
        default="gpt-4o-mini-tts", pattern=r"^[A-Za-z0-9._-]{1,100}$"
    )
    openai_speech_voice: str = Field(default="coral", pattern=r"^[a-z]{1,30}$")
    openai_timeout_seconds: int = Field(default=45, ge=5, le=120)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key.get_secret_value().strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
