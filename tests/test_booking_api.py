from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import api
from app.db import Base, get_db
from app.dialogue.manager import DialogueManager
from app.dialogue.translations import LANGUAGES
from app.models import Appointment

BOOKING_SAMPLES = [
    ("en-US", "Christopher Bell", "General medicine", "yes"),
    ("si-LK", "හරිත් පෙරේරා", "සාමාන්‍ය වෛද්‍ය", "ඔව්"),
    ("ta-LK", "குமார்", "பொது மருத்துவம்", "ஆம்"),
    ("hi-IN", "जीवन कुमार", "सामान्य चिकित्सा", "हाँ"),
    ("es-ES", "Lucía García", "Medicina general", "sí"),
    ("fr-FR", "Élodie Martin", "Médecine générale", "oui"),
    ("de-DE", "Jasmin Müller", "Allgemeinmedizin", "ja"),
    ("ar-SA", "ليلى أحمد", "الطب العام", "نعم"),
    ("zh-CN", "王小明", "全科", "是"),
    ("ja-JP", "大野真人", "一般内科", "はい"),
]


@pytest.fixture
def booking_api(monkeypatch):
    # All tables, connections and conversation state belong to this test only.
    # Importing app.main would create tables in the user's configured database.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(api, "dialogue_manager", DialogueManager())

    def test_database():
        with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_db] = test_database
    with TestClient(app) as client:
        yield client, sessions
    engine.dispose()


def _row_count(sessions):
    with sessions() as session:
        return session.scalar(select(func.count(Appointment.id)))


def _start(client, locale="en-US"):
    response = client.post("/api/sessions", json={"language_locale": locale})
    assert response.status_code == 200
    payload = response.json()
    session_uuid = UUID(payload["session_id"])
    assert str(session_uuid) == payload["session_id"]
    assert session_uuid.version == 4
    assert payload["assistant_text"] == LANGUAGES[locale].prompts["greeting"]
    assert payload["step"] == "patient_name"
    return payload["session_id"]


def _send(client, session_id, text, locale="en-US", expected_status=200):
    response = client.post(
        "/api/messages",
        json={"session_id": session_id, "language_locale": locale, "text": text},
    )
    assert response.status_code == expected_status, response.text
    return response.json()


def _reach_time(client, session_id, locale="en-US", name="Demo Patient", specialty="Dental"):
    appointment_date = (date.today() + timedelta(days=7)).isoformat()
    for text, step in [
        (name, "specialty"),
        (specialty, "appointment_date"),
        (appointment_date, "appointment_time"),
    ]:
        result = _send(client, session_id, text, locale)
        assert result["step"] == step
        assert result["status"] == "active"
        assert result["booking"] is None
    return appointment_date


@pytest.mark.parametrize("locale,name,specialty,yes", BOOKING_SAMPLES)
def test_localized_api_booking_serializes_and_persists_once(
    booking_api, locale, name, specialty, yes
):
    client, sessions = booking_api
    session_id = _start(client, locale)
    appointment_date = _reach_time(client, session_id, locale, name, specialty)
    assert _send(client, session_id, "10:30", locale)["step"] == "confirm"
    assert _row_count(sessions) == 0

    result = _send(client, session_id, yes, locale)
    assert result["status"] == "booked"
    assert result["step"] == "done"
    booking = result["booking"]
    assert str(UUID(booking["public_id"])) == booking["public_id"]
    assert booking == {
        "public_id": booking["public_id"],
        "patient_name": name,
        "specialty": specialty,
        "appointment_date": appointment_date,
        "appointment_time": "10:30",
        "language_locale": locale,
    }
    assert booking["public_id"][-8:].upper() in result["assistant_text"]
    with sessions() as database:
        row = database.scalars(select(Appointment)).one()
        assert row.public_id == booking["public_id"]
        assert row.patient_name == name
        assert row.specialty == specialty
        assert row.language_locale == locale
        assert row.appointment_date.isoformat() == appointment_date
        assert row.appointment_time.strftime("%H:%M") == "10:30"
        assert row.status == "booked"

    # Network retries and later cancel words cannot create/delete another booking.
    assert _send(client, session_id, yes, locale) == result
    assert _send(client, session_id, sorted(LANGUAGES[locale].cancel_words)[0], locale) == result
    assert _row_count(sessions) == 1


def test_occupied_slot_is_rejected_and_alternative_can_be_booked(booking_api):
    client, sessions = booking_api
    first = _start(client)
    _reach_time(client, first)
    assert _send(client, first, "10:30")["step"] == "confirm"
    original = _send(client, first, "yes")

    second = _start(client)
    _reach_time(client, second, name="Second Patient")
    unavailable = _send(client, second, "10:30")
    assert unavailable["step"] == "appointment_time"
    assert unavailable["assistant_text"] == LANGUAGES["en-US"].prompts["slot_taken"]
    assert unavailable["booking"] is None
    assert _row_count(sessions) == 1
    assert _send(client, second, "11:30")["step"] == "confirm"
    alternative = _send(client, second, "yes")
    assert alternative["status"] == "booked"
    assert alternative["booking"]["public_id"] != original["booking"]["public_id"]
    assert alternative["booking"]["appointment_time"] == "11:30"
    assert _row_count(sessions) == 2


def test_slot_is_rechecked_when_two_conversations_confirm_the_same_time(booking_api):
    client, sessions = booking_api
    first, second = _start(client), _start(client)
    for session_id in (first, second):
        _reach_time(client, session_id)
        assert _send(client, session_id, "10:30")["step"] == "confirm"

    booked = _send(client, first, "yes")
    assert booked["status"] == "booked"
    conflict = _send(client, second, "yes")
    assert conflict["status"] == "active"
    assert conflict["step"] == "appointment_time"
    assert conflict["booking"] is None
    assert _send(client, first, "yes") == booked
    assert _row_count(sessions) == 1


def test_database_unique_constraint_survives_stale_availability_and_rolls_back(
    booking_api, monkeypatch
):
    client, sessions = booking_api
    first = _start(client)
    _reach_time(client, first)
    _send(client, first, "10:30")
    assert _send(client, first, "yes")["status"] == "booked"

    # Simulate another writer taking a slot after an optimistic availability read.
    # The real repository and SQLite unique constraint remain in use.
    monkeypatch.setattr(api, "is_slot_available", lambda *_args: True)
    second = _start(client)
    _reach_time(client, second)
    assert _send(client, second, "10:30")["step"] == "confirm"
    conflict = _send(client, second, "yes", expected_status=409)
    assert conflict == {"detail": "Appointment slot is no longer available"}
    assert _row_count(sessions) == 1

    assert _send(client, second, "no")["step"] == "appointment_time"
    assert _send(client, second, "11:30")["step"] == "confirm"
    assert _send(client, second, "yes")["status"] == "booked"
    assert _row_count(sessions) == 2


@pytest.mark.parametrize("locale", LANGUAGES)
@pytest.mark.parametrize(
    "command_group,status,prompt",
    [
        ("cancel_words", "cancelled", "cancelled"),
        ("human_words", "transfer_requested", "transfer"),
        ("emergency_words", "transfer_requested", "emergency"),
    ],
)
def test_terminal_commands_never_persist_and_require_restart(
    booking_api, locale, command_group, status, prompt
):
    client, sessions = booking_api
    session_id = _start(client, locale)
    _reach_time(client, session_id, locale)
    assert _send(client, session_id, "10:30", locale)["step"] == "confirm"
    language = LANGUAGES[locale]
    command = sorted(getattr(language, command_group))[0]
    stopped = _send(client, session_id, command, locale)
    assert stopped["status"] == status
    assert stopped["assistant_text"] == language.prompts[prompt]
    assert stopped["booking"] is None
    assert _send(client, session_id, sorted(language.yes_words)[0], locale) == stopped
    assert _send(client, session_id, "Second Patient", locale) == stopped
    assert _row_count(sessions) == 0

    restarted = _send(client, session_id, sorted(language.restart_words)[0], locale)
    assert restarted["status"] == "active"
    assert restarted["step"] == "patient_name"
    assert _send(client, session_id, "New Patient", locale)["step"] == "specialty"
    assert _row_count(sessions) == 0


def test_restart_after_booking_preserves_original_and_allows_a_new_slot(booking_api):
    client, sessions = booking_api
    session_id = _start(client)
    _reach_time(client, session_id)
    _send(client, session_id, "10:30")
    original = _send(client, session_id, "yes")
    assert _send(client, session_id, "restart")["step"] == "patient_name"
    assert _row_count(sessions) == 1
    _reach_time(client, session_id, name="New Patient")
    _send(client, session_id, "11:30")
    second = _send(client, session_id, "yes")
    assert second["booking"]["public_id"] != original["booking"]["public_id"]
    assert _row_count(sessions) == 2


@pytest.mark.parametrize(
    "changed_field,value,status",
    [
        ("session_id", "invalid", 422),
        ("session_id", "x" * 36, 400),
        ("language_locale", "xx-XX", 422),
        ("text", "", 422),
        ("text", "   ", 422),
        ("text", "x" * 501, 422),
    ],
)
def test_invalid_api_inputs_do_not_change_conversation_or_database(
    booking_api, changed_field, value, status
):
    client, sessions = booking_api
    session_id = _start(client)
    payload = {"session_id": session_id, "language_locale": "en-US", "text": "Demo Patient"}
    payload[changed_field] = value
    response = client.post("/api/messages", json=payload)
    assert response.status_code == status
    assert _row_count(sessions) == 0
    assert _send(client, session_id, "Valid Patient")["step"] == "specialty"


def test_unknown_uuid_cannot_fix_or_create_a_session(booking_api):
    client, sessions = booking_api
    real_session_id = _start(client)
    response = client.post(
        "/api/messages",
        json={
            "session_id": str(uuid4()),
            "language_locale": "en-US",
            "text": "Injected Patient",
        },
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Session not found or expired"}
    assert _row_count(sessions) == 0
    assert _send(client, real_session_id, "Valid Patient")["step"] == "specialty"


def test_sql_injection_shaped_fields_are_stored_as_literal_data(booking_api):
    client, sessions = booking_api
    patient_name = "Robert'); DROP TABLE appointments; --"
    specialty = "Dental'); DELETE FROM appointments; --"
    session_id = _start(client)
    _reach_time(client, session_id, name=patient_name, specialty=specialty)
    _send(client, session_id, "10:30")
    booked = _send(client, session_id, "yes")

    assert booked["booking"]["patient_name"] == patient_name
    assert booked["booking"]["specialty"] == specialty
    with sessions() as database:
        row = database.scalars(select(Appointment)).one()
        assert row.patient_name == patient_name
        assert row.specialty == specialty
        assert database.scalar(select(func.count(Appointment.id))) == 1

    # A second insert proves the appointments table and its constraint remain usable.
    second_session_id = _start(client)
    _reach_time(client, second_session_id, name="Second Patient")
    _send(client, second_session_id, "11:30")
    assert _send(client, second_session_id, "yes")["status"] == "booked"
    assert _row_count(sessions) == 2


def test_xss_shaped_fields_are_returned_as_json_data(booking_api):
    client, _ = booking_api
    patient_name = "</script><img src=x onerror=alert(1)>"
    specialty = "\"><svg/onload=alert(1)>"
    session_id = _start(client)
    _reach_time(client, session_id, name=patient_name, specialty=specialty)
    response = client.post(
        "/api/messages",
        json={"session_id": session_id, "language_locale": "en-US", "text": "10:30"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert patient_name in response.json()["assistant_text"]
    assert specialty in response.json()["assistant_text"]


def test_invalid_booking_values_stay_at_the_relevant_step(booking_api):
    client, sessions = booking_api
    session_id = _start(client)
    assert _send(client, session_id, "A")["step"] == "patient_name"
    assert _send(client, session_id, "  Demo   Patient  ")["step"] == "specialty"
    assert _send(client, session_id, "D")["step"] == "specialty"
    assert _send(client, session_id, "Dental")["step"] == "appointment_date"
    for invalid_date in (
        "2026-02-30",
        (date.today() - timedelta(days=1)).isoformat(),
        (date.today() + timedelta(days=366)).isoformat(),
    ):
        result = _send(client, session_id, invalid_date)
        assert result["step"] == "appointment_date"
        assert result["assistant_text"] == LANGUAGES["en-US"].prompts["invalid_date"]

    future_date = (date.today() + timedelta(days=7)).isoformat()
    assert _send(client, session_id, future_date)["step"] == "appointment_time"
    for invalid_time in ("07:59", "17:01", "25:00", "09:60"):
        result = _send(client, session_id, invalid_time)
        assert result["step"] == "appointment_time"
        assert result["assistant_text"] == LANGUAGES["en-US"].prompts["invalid_time"]
    assert _send(client, session_id, "10:30")["step"] == "confirm"
    assert _send(client, session_id, "yesterday")["step"] == "confirm"
    assert _send(client, session_id, "No, don't book")["step"] == "appointment_time"
    assert _row_count(sessions) == 0
    _send(client, session_id, "11:30")
    booked = _send(client, session_id, "yes")
    assert booked["booking"]["patient_name"] == "Demo Patient"
    assert booked["booking"]["appointment_time"] == "11:30"
    assert _row_count(sessions) == 1
