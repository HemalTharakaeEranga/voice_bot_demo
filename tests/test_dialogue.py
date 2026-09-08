from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app.dialogue.manager import DialogueManager, SessionNotFoundError
from app.dialogue.translations import LANGUAGES
from app.dialogue.validators import parse_appointment_date, parse_appointment_time

LANGUAGE_SAMPLES = [
    ("en-US", "Christopher Bell", "General medicine", "Yes, please", "No, don't book"),
    ("si-LK", "හරිත් පෙරේරා", "සාමාන්‍ය වෛද්‍ය", "ඔව්.", "නැහැ"),
    ("ta-LK", "குமார்", "பொது மருத்துவம்", "ஆம்!", "இல்லை"),
    ("hi-IN", "जीवन कुमार", "सामान्य चिकित्सा", "हाँ।", "नहीं"),
    ("es-ES", "Lucía García", "Medicina general", "Sí, por favor", "No, correcto no"),
    ("fr-FR", "Élodie Martin", "Médecine générale", "Oui, merci", "Ce n'est pas correct"),
    ("de-DE", "Jasmin Müller", "Allgemeinmedizin", "Ja, bitte", "Nicht richtig"),
    ("ar-SA", "ليلى أحمد", "الطب العام", "نعم،", "لا، ليس صحيح"),
    ("zh-CN", "王小明", "全科", "是的，谢谢", "不是"),
    ("ja-JP", "大野真人", "一般内科", "はい、お願いします", "いいえ、変更してください"),
]


def _saved_booking(payload):
    return {
        "public_id": str(uuid4()),
        "patient_name": str(payload["patient_name"]),
        "specialty": str(payload["specialty"]),
        "appointment_date": payload["appointment_date"].isoformat(),
        "appointment_time": payload["appointment_time"].strftime("%H:%M"),
        "language_locale": str(payload["language_locale"]),
    }


def _confirmation_session(locale="en-US", name="Demo Patient", specialty="Dental"):
    manager = DialogueManager()
    session_id = str(uuid4())
    manager.start_session(session_id, locale)
    saved = []

    def send(message):
        def save(payload):
            saved.append(payload)
            return _saved_booking(payload)

        return manager.process_message(session_id, locale, message, lambda *_: True, save)

    assert send(name).step == "specialty"
    assert send(specialty).step == "appointment_date"
    assert send((date.today() + timedelta(days=7)).isoformat()).step == "appointment_time"
    assert send("10:30").step == "confirm"
    return send, saved


def test_unknown_session_is_rejected_without_running_database_callbacks():
    manager = DialogueManager()

    def unexpected_callback(*_args):
        pytest.fail("Unknown sessions must not reach database callbacks")

    with pytest.raises(SessionNotFoundError):
        manager.process_message(
            str(uuid4()),
            "en-US",
            "Demo Patient",
            unexpected_callback,
            unexpected_callback,
        )


def test_terminal_session_replay_refreshes_access_until_ttl_expires():
    current_time = [100.0]
    manager = DialogueManager(session_ttl_seconds=10, clock=lambda: current_time[0])
    session_id = str(uuid4())
    manager.start_session(session_id, "en-US")
    terminal = manager.process_message(
        session_id,
        "en-US",
        "human",
        lambda *_: True,
        _saved_booking,
    )

    current_time[0] += 9
    assert (
        manager.process_message(
            session_id,
            "en-US",
            "still there",
            lambda *_: True,
            _saved_booking,
        )
        == terminal
    )

    current_time[0] += 10
    with pytest.raises(SessionNotFoundError):
        manager.process_message(
            session_id,
            "en-US",
            "still there",
            lambda *_: True,
            _saved_booking,
        )


def test_session_capacity_evicts_the_least_recently_used_session():
    current_time = [0.0]
    manager = DialogueManager(max_sessions=2, clock=lambda: current_time[0])
    first, second, third = (str(uuid4()) for _ in range(3))
    manager.start_session(first, "en-US")
    current_time[0] += 1
    manager.start_session(second, "en-US")
    current_time[0] += 1
    manager.process_message(first, "en-US", "First Patient", lambda *_: True, _saved_booking)
    current_time[0] += 1
    manager.start_session(third, "en-US")

    with pytest.raises(SessionNotFoundError):
        manager.process_message(second, "en-US", "test", lambda *_: True, _saved_booking)
    assert (
        manager.process_message(first, "en-US", "Dental", lambda *_: True, _saved_booking).step
        == "appointment_date"
    )
    third_result = manager.process_message(
        third, "en-US", "Third Patient", lambda *_: True, _saved_booking
    )
    assert third_result.step == "specialty"


def test_complete_booking_flow():
    manager = DialogueManager()
    session_id = str(uuid4())
    manager.start_session(session_id, "en-US")

    saved = {}

    def available(_date, _time):
        return True

    def save(payload):
        saved.update(payload)
        return {
            "public_id": str(uuid4()),
            "patient_name": str(payload["patient_name"]),
            "specialty": str(payload["specialty"]),
            "appointment_date": payload["appointment_date"].isoformat(),
            "appointment_time": payload["appointment_time"].strftime("%H:%M"),
            "language_locale": str(payload["language_locale"]),
        }

    assert (
        manager.process_message(session_id, "en-US", "Demo Patient", available, save).step
        == "specialty"
    )
    assert (
        manager.process_message(session_id, "en-US", "Cardiology", available, save).step
        == "appointment_date"
    )

    future_date = (date.today() + timedelta(days=7)).isoformat()
    assert (
        manager.process_message(session_id, "en-US", future_date, available, save).step
        == "appointment_time"
    )
    assert manager.process_message(session_id, "en-US", "10:30", available, save).step == "confirm"

    result = manager.process_message(session_id, "en-US", "yes", available, save)
    assert result.status == "booked"
    assert saved["patient_name"] == "Demo Patient"


def test_rejects_invalid_time():
    manager = DialogueManager()
    session_id = str(uuid4())
    manager.start_session(session_id, "en-US")
    manager.process_message(session_id, "en-US", "Demo Patient", lambda *_: True, lambda x: x)
    manager.process_message(session_id, "en-US", "Dental", lambda *_: True, lambda x: x)
    future_date = (date.today() + timedelta(days=3)).isoformat()
    manager.process_message(session_id, "en-US", future_date, lambda *_: True, lambda x: x)

    result = manager.process_message(session_id, "en-US", "22:15", lambda *_: True, lambda x: x)
    assert result.step == "appointment_time"
    assert "08:00" in result.assistant_text


def test_human_transfer_command():
    manager = DialogueManager()
    session_id = str(uuid4())
    manager.start_session(session_id, "en-US")
    result = manager.process_message(
        session_id, "en-US", "I need a human", lambda *_: True, lambda x: x
    )
    assert result.status == "transfer_requested"


@pytest.mark.parametrize("locale,name,specialty,yes,no", LANGUAGE_SAMPLES)
def test_all_ten_languages_book_and_replay_once(locale, name, specialty, yes, no):
    send, saved = _confirmation_session(locale, name, specialty)
    result = send(yes)
    assert result.status == "booked"
    assert result.step == "done"
    assert result.booking["patient_name"] == name
    assert result.booking["language_locale"] == locale
    assert send(yes) == result
    # A later cancel command cannot claim an existing booking was never created.
    assert send(next(iter(LANGUAGES[locale].cancel_words))) == result
    assert len(saved) == 1


@pytest.mark.parametrize("locale,name,specialty,yes,no", LANGUAGE_SAMPLES)
def test_localized_negative_confirmation_never_books(locale, name, specialty, yes, no):
    send, saved = _confirmation_session(locale, name, specialty)
    result = send(no)
    assert result.step == "appointment_time"
    assert result.status == "active"
    assert not saved
    assert send("11:30").step == "confirm"
    assert send(yes).status == "booked"


@pytest.mark.parametrize("locale", LANGUAGES)
@pytest.mark.parametrize(
    "command_group,status",
    [("cancel_words", "cancelled"), ("human_words", "transfer_requested")],
)
def test_terminal_commands_stop_flow_until_explicit_restart(locale, command_group, status):
    send, saved = _confirmation_session(locale)
    language = LANGUAGES[locale]
    result = send(sorted(getattr(language, command_group))[0])
    assert result.status == status
    assert send(sorted(language.yes_words)[0]) == result
    assert not saved
    restarted = send(sorted(language.restart_words)[0])
    assert restarted.status == "active"
    assert restarted.step == "patient_name"
    assert send("Demo Patient").step == "specialty"


@pytest.mark.parametrize("locale", LANGUAGES)
def test_emergency_commands_stop_booking_in_every_language(locale):
    send, saved = _confirmation_session(locale)
    result = send(sorted(LANGUAGES[locale].emergency_words)[0])
    assert result.status == "transfer_requested"
    assert result.assistant_text == LANGUAGES[locale].prompts["emergency"]
    assert send(sorted(LANGUAGES[locale].yes_words)[0]) == result
    assert not saved


@pytest.mark.parametrize(
    "locale,message",
    [
        ("en-US", "yesterday"),
        ("en-US", "notebook"),
        ("en-US", "unconfirmed"),
        ("de-DE", "Jasmin"),
        ("es-ES", "Sierra"),
        ("hi-IN", "जीवन"),
        ("si-LK", "හරිත්"),
    ],
)
def test_confirmation_keywords_do_not_match_inside_words(locale, message):
    send, saved = _confirmation_session(locale)
    result = send(message)
    assert result.step == "confirm"
    assert result.status == "active"
    assert not saved


def test_decomposed_accents_and_curly_apostrophe_confirmation():
    send, saved = _confirmation_session("es-ES")
    assert send("Si\u0301, por favor").status == "booked"
    assert len(saved) == 1
    send, saved = _confirmation_session()
    assert send("I don’t want to book").step == "appointment_time"
    assert not saved


@pytest.mark.parametrize(
    "locale,message",
    [
        ("en-US", "I cannot book"),
        ("en-US", "I can't confirm"),
        ("zh-CN", "没有确认"),
        ("ja-JP", "はいではない"),
        ("ja-JP", "確認しないで"),
    ],
)
def test_negated_positive_words_never_book(locale, message):
    send, saved = _confirmation_session(locale)
    assert send(message).step == "appointment_time"
    assert not saved


@pytest.mark.parametrize(
    "locale,message",
    [("de-DE", "Ich habe Brustschmerzen"), ("hi-IN", "यह आपातकाल है")],
)
def test_common_emergency_inflections_are_recognized(locale, message):
    send, saved = _confirmation_session(locale)
    assert send(message).status == "transfer_requested"
    assert not saved


@pytest.mark.parametrize(
    "digits", ["0123456789", "٠١٢٣٤٥٦٧٨٩", "०१२३४५६७८९", "０１２３４５６７８９"]
)
@pytest.mark.parametrize("separator", ["-", " ", "/"])
def test_numeric_dates_accept_localized_digits_and_year_first_separators(digits, separator):
    expected = date.today() + timedelta(days=7)
    value = expected.isoformat().replace("-", separator)
    value = value.translate(str.maketrans("0123456789", digits))
    assert parse_appointment_date(value) == expected


@pytest.mark.parametrize(
    "locale,value",
    [
        ("en-US", "September 23"),
        ("en-US", "Sep. 23rd, please"),
        ("en-US", "23 September"),
        ("si-LK", "සැප්තැම්බර් 23"),
        ("ta-LK", "செப்டம்பர் 23"),
        ("hi-IN", "23 सितंबर"),
        ("es-ES", "23 de septiembre"),
        ("fr-FR", "23 septembre"),
        ("de-DE", "23. September"),
        ("ar-SA", "٢٣ سبتمبر"),
        ("zh-CN", "九月二十三日"),
        ("ja-JP", "9月23日"),
    ],
)
def test_spoken_september_dates_are_recognized(locale, value):
    reference = date(2026, 9, 8)
    assert parse_appointment_date(value, locale, reference_date=reference) == date(2026, 9, 23)


@pytest.mark.parametrize("value", ["9/23", "9-23", "9 23", "09/23."])
def test_unambiguous_yearless_numeric_date_uses_next_occurrence(value):
    reference = date(2026, 9, 24)
    assert parse_appointment_date(value, reference_date=reference) == date(2027, 9, 23)


def test_ambiguous_yearless_numeric_date_uses_explicit_locale_order():
    reference = date(2026, 1, 1)
    assert parse_appointment_date("3/11", "en-US", reference_date=reference) == date(2026, 3, 11)
    assert parse_appointment_date("3/11", "fr-FR", reference_date=reference) == date(2026, 11, 3)


def test_iso_date_accepts_terminal_speech_punctuation():
    reference = date(2026, 9, 8)
    assert parse_appointment_date(
        "2026-09-23.", reference_date=reference
    ) == date(2026, 9, 23)


@pytest.mark.parametrize(
    "value", ["09:30", "9:30", "09 30", "09.30", "٠٩:٣٠", "०९:३०", "０９：３０"]
)
def test_numeric_times_accept_localized_digits(value):
    parsed = parse_appointment_time(value)
    assert parsed is not None
    assert parsed.strftime("%H:%M") == "09:30"


@pytest.mark.parametrize(
    "locale,value,expected",
    [
        ("en-US", "9:30 AM.", "09:30"),
        ("en-US", "9 AM", "09:00"),
        ("en-US", "5 PM", "17:00"),
        ("en-US", "9:30am", "09:30"),
        ("en-US", "4pm", "16:00"),
        ("si-LK", "ප.ව. 4:30", "16:30"),
        ("ta-LK", "மாலை 4:30", "16:30"),
        ("hi-IN", "शाम 4:30 बजे", "16:30"),
        ("es-ES", "4:30 de la tarde", "16:30"),
        ("fr-FR", "16 h 30", "16:30"),
        ("fr-FR", "9h30", "09:30"),
        ("de-DE", "16:30 Uhr", "16:30"),
        ("ar-SA", "٤:٣٠ مساءً", "16:30"),
        ("zh-CN", "下午4点30分", "16:30"),
        ("ja-JP", "午後4時30分", "16:30"),
    ],
)
def test_spoken_time_formats_across_supported_languages(locale, value, expected):
    parsed = parse_appointment_time(value, locale)
    assert parsed is not None
    assert parsed.strftime("%H:%M") == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("nine thirty", "09:30"),
        ("ten o'clock", "10:00"),
        ("half past ten", "10:30"),
        ("half to nine", "08:30"),
        ("quarter to five PM", "16:45"),
    ],
)
def test_common_english_spoken_times(value, expected):
    parsed = parse_appointment_time(value)
    assert parsed is not None
    assert parsed.strftime("%H:%M") == expected


@pytest.mark.parametrize(
    "value",
    ["07:59", "17:01", "24:00", "09:60", "7 AM", "5:01 PM", "9 AM PM"],
)
def test_time_limits_still_apply(value):
    assert parse_appointment_time(value) is None


def test_date_limits_and_unambiguous_format_still_apply():
    assert parse_appointment_date((date.today() - timedelta(days=1)).isoformat()) is None
    assert parse_appointment_date((date.today() + timedelta(days=366)).isoformat()) is None
    assert parse_appointment_date("09/10/2026") is None
    assert parse_appointment_date("2026-02-30") is None


def test_same_day_past_time_is_rejected_using_backend_wall_clock():
    manager = DialogueManager(wall_clock=lambda: datetime(2026, 9, 23, 10, 0))
    session_id = str(uuid4())
    manager.start_session(session_id, "en-US")

    def send(value):
        return manager.process_message(
            session_id,
            "en-US",
            value,
            lambda *_: True,
            _saved_booking,
        )

    assert send("Demo Patient").step == "specialty"
    assert send("Dental").step == "appointment_date"
    assert send("September 23").step == "appointment_time"
    assert send("9:30 AM").step == "appointment_time"
    assert send("10 AM").step == "appointment_time"
    assert send("10:30 AM").step == "confirm"


def test_slot_is_rechecked_against_wall_clock_at_confirmation():
    current = [datetime(2026, 9, 23, 9, 0)]
    manager = DialogueManager(wall_clock=lambda: current[0])
    session_id = str(uuid4())
    manager.start_session(session_id, "en-US")

    def send(value):
        return manager.process_message(
            session_id,
            "en-US",
            value,
            lambda *_: True,
            _saved_booking,
        )

    for value, step in [
        ("Demo Patient", "specialty"),
        ("Dental", "appointment_date"),
        ("September 23", "appointment_time"),
        ("9:30 AM", "confirm"),
    ]:
        assert send(value).step == step
    current[0] = datetime(2026, 9, 23, 9, 31)
    assert send("yes").step == "appointment_time"


def test_slot_taken_at_confirmation_does_not_save_booking():
    manager = DialogueManager()
    session_id = str(uuid4())
    manager.start_session(session_id, "en-US")
    for value in [
        "Demo Patient",
        "Dental",
        (date.today() + timedelta(days=7)).isoformat(),
        "10:30",
    ]:
        manager.process_message(session_id, "en-US", value, lambda *_: True, _saved_booking)

    def unexpected_save(_payload):
        pytest.fail("A conflicting appointment must not be saved")

    result = manager.process_message(session_id, "en-US", "yes", lambda *_: False, unexpected_save)
    assert result.step == "appointment_time"
    assert result.status == "active"
