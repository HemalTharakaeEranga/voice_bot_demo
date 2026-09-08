import pytest
from pydantic import ValidationError

from app.config import Settings


def test_clinic_offset_defaults_to_sri_lanka(monkeypatch):
    monkeypatch.delenv("CLINIC_UTC_OFFSET_MINUTES", raising=False)
    settings = Settings(_env_file=None)
    assert settings.clinic_utc_offset_minutes == 330


@pytest.mark.parametrize("offset", [-721, 841])
def test_clinic_offset_rejects_values_outside_real_utc_offset_range(offset):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, clinic_utc_offset_minutes=offset)
