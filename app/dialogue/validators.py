import re
import unicodedata
from datetime import date, time, timedelta

DATE_PATTERN = re.compile(r"^([0-9]{4})[-/\s]([0-9]{1,2})[-/\s]([0-9]{1,2})$")
TIME_PATTERN = re.compile(r"^([0-9]{1,2})[:.\s]([0-9]{2})$")


def normalize_input(raw_value: str) -> str:
    """Keep language text intact while normalizing speech/keyboard variants."""
    value = unicodedata.normalize("NFKC", raw_value).replace("’", "'")
    return " ".join(value.strip().split())


def _normalize_number_input(raw_value: str) -> str:
    # Arabic, Indic and full-width digits should work just like ASCII digits.
    value = normalize_input(raw_value)
    return "".join(
        str(unicodedata.decimal(character)) if character.isdecimal() else character
        for character in value
        if unicodedata.category(character) != "Cf"
    )


def parse_appointment_date(raw_value: str) -> date | None:
    match = DATE_PATTERN.fullmatch(_normalize_number_input(raw_value))
    if not match:
        return None
    try:
        parsed = date(*(int(part) for part in match.groups()))
    except ValueError:
        return None

    today = date.today()
    if parsed < today or parsed > today + timedelta(days=365):
        return None
    return parsed


def parse_appointment_time(raw_value: str) -> time | None:
    match = TIME_PATTERN.fullmatch(_normalize_number_input(raw_value))
    if not match:
        return None
    try:
        parsed = time(*(int(part) for part in match.groups()))
    except ValueError:
        return None

    if parsed < time(8, 0) or parsed > time(17, 0):
        return None
    return parsed


def sanitize_slot_text(raw_value: str, max_length: int = 80) -> str:
    cleaned = " ".join(raw_value.strip().split())
    return cleaned[:max_length]
