from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.dialogue.translations import SUPPORTED_LANGUAGE_LOCALES


class StartSessionRequest(BaseModel):
    language_locale: str = Field(default="en-US", max_length=16)

    @field_validator("language_locale")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if value not in SUPPORTED_LANGUAGE_LOCALES:
            raise ValueError("Unsupported language locale")
        return value


class StartSessionResponse(BaseModel):
    session_id: str
    assistant_text: str
    step: str


class MessageRequest(BaseModel):
    session_id: str = Field(min_length=36, max_length=36)
    language_locale: str = Field(max_length=16)
    text: str = Field(min_length=1, max_length=500)

    @field_validator("language_locale")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if value not in SUPPORTED_LANGUAGE_LOCALES:
            raise ValueError("Unsupported language locale")
        return value

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Message cannot be empty")
        return normalized


class BookingSummary(BaseModel):
    public_id: str
    patient_name: str
    specialty: str
    appointment_date: str
    appointment_time: str
    language_locale: str


class MessageResponse(BaseModel):
    assistant_text: str
    step: str
    status: Literal["active", "booked", "cancelled", "transfer_requested"]
    booking: BookingSummary | None = None
