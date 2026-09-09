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


@pytest.mark.parametrize(
    "locale,value,expected_day",
    [
        ("en-US", "September 09", 9),
        ("en-US", "September 09, 2026", 9),
        ("en-US", "September ninth", 9),
        ("en-US", "September twenty third", 23),
        ("si-LK", "සැප්තැම්බර් විසි තුන", 23),
        ("ta-LK", "செப்டம்பர் இருபத்து மூன்று", 23),
        ("hi-IN", "सितंबर तेईस", 23),
        ("es-ES", "veintitrés de septiembre", 23),
        ("fr-FR", "vingt-trois septembre", 23),
        ("de-DE", "dreiundzwanzigsten September", 23),
        ("ar-SA", "الثالث والعشرين من سبتمبر", 23),
        ("zh-CN", "九月二十三日", 23),
        ("ja-JP", "九月二十三日", 23),
    ],
)
def test_spoken_day_words_are_recognized_without_partial_matching(
    locale, value, expected_day
):
    reference = date(2026, 9, 8)
    assert parse_appointment_date(value, locale, reference_date=reference) == date(
        2026, 9, expected_day
    )


@pytest.mark.parametrize(
    "locale,month,day_words_text",
    [
        (
            "si-LK",
            "ඔක්තෝබර්",
            "දහතුන|දහහතර|පහළොව|දහසය|දහහත|දහඅට|දහනවය|විස්ස|විසි එක|"
            "විසි දෙක|විසි තුන|විසි හතර|විසි පහ|විසි හය|විසි හත|විසි අට|"
            "විසි නවය|තිහ|තිස් එක",
        ),
        (
            "ta-LK",
            "அக்டோபர்",
            "பதின்மூன்று|பதினான்கு|பதினைந்து|பதினாறு|பதினேழு|பதினெட்டு|"
            "பத்தொன்பது|இருபது|இருபத்தொன்று|இருபத்திரண்டு|இருபத்துமூன்று|"
            "இருபத்துநான்கு|இருபத்தைந்து|இருபத்தாறு|இருபத்தேழு|இருபத்தெட்டு|"
            "இருபத்தொன்பது|முப்பது|முப்பத்தொன்று",
        ),
        (
            "hi-IN",
            "अक्टूबर",
            "तेरह|चौदह|पंद्रह|सोलह|सत्रह|अठारह|उन्नीस|बीस|इक्कीस|बाईस|तेईस|"
            "चौबीस|पच्चीस|छब्बीस|सत्ताईस|अट्ठाईस|उनतीस|तीस|इकतीस",
        ),
        (
            "es-ES",
            "octubre",
            "trece|catorce|quince|dieciséis|diecisiete|dieciocho|diecinueve|"
            "veinte|veintiuno|veintidós|veintitrés|veinticuatro|veinticinco|"
            "veintiséis|veintisiete|veintiocho|veintinueve|treinta|treinta y uno",
        ),
        (
            "fr-FR",
            "octobre",
            "treize|quatorze|quinze|seize|dix-sept|dix-huit|dix-neuf|vingt|"
            "vingt et un|vingt-deux|vingt-trois|vingt-quatre|vingt-cinq|vingt-six|"
            "vingt-sept|vingt-huit|vingt-neuf|trente|trente et un",
        ),
        (
            "de-DE",
            "Oktober",
            "dreizehnten|vierzehnten|fünfzehnten|sechzehnten|siebzehnten|"
            "achtzehnten|neunzehnten|zwanzigsten|einundzwanzigsten|"
            "zweiundzwanzigsten|dreiundzwanzigsten|vierundzwanzigsten|"
            "fünfundzwanzigsten|sechsundzwanzigsten|siebenundzwanzigsten|"
            "achtundzwanzigsten|neunundzwanzigsten|dreißigsten|einunddreißigsten",
        ),
        (
            "ar-SA",
            "أكتوبر",
            "الثالث عشر|الرابع عشر|الخامس عشر|السادس عشر|السابع عشر|الثامن عشر|"
            "التاسع عشر|العشرين|الحادي والعشرين|الثاني والعشرين|الثالث والعشرين|"
            "الرابع والعشرين|الخامس والعشرين|السادس والعشرين|السابع والعشرين|"
            "الثامن والعشرين|التاسع والعشرين|الثلاثين|الحادي والثلاثين",
        ),
    ],
)
def test_localized_spoken_days_cover_thirteen_through_thirty_one(
    locale, month, day_words_text
):
    reference = date(2026, 9, 1)
    day_words = day_words_text.split("|")
    assert len(day_words) == 19
    for expected_day, day_words_value in enumerate(day_words, start=13):
        if locale == "de-DE":
            spoken_date = f"am {day_words_value} {month}"
        elif locale == "ar-SA":
            spoken_date = f"في {day_words_value} من {month}"
        elif locale == "es-ES":
            spoken_date = f"{day_words_value} de {month}"
        else:
            spoken_date = f"{month} {day_words_value}"
        assert parse_appointment_date(
            spoken_date, locale, reference_date=reference
        ) == date(2026, 10, expected_day)


@pytest.mark.parametrize("value", ["9/23", "9-23", "9 23", "09/23."])
def test_unambiguous_yearless_numeric_date_uses_next_occurrence(value):
    reference = date(2026, 9, 24)
    assert parse_appointment_date(value, reference_date=reference) == date(2027, 9, 23)


@pytest.mark.parametrize(
    "value", ["2026/09/23", "2026-09-23", "2026.09.23", "2026 09 23"]
)
def test_year_first_date_accepts_common_separator_variants(value):
    reference = date(2026, 9, 8)
    assert parse_appointment_date(value, reference_date=reference) == date(2026, 9, 23)


@pytest.mark.parametrize(
    "locale,value",
    [
        ("en-US", "09/23/2026"),
        ("en-US", "09-23-2026"),
        ("si-LK", "23/09/2026"),
        ("ta-LK", "23-09-2026"),
        ("hi-IN", "23.09.2026"),
        ("es-ES", "23 09 2026"),
        ("fr-FR", "23/09/2026"),
        ("de-DE", "23.09.2026"),
        ("ar-SA", "٢٣/٠٩/٢٠٢٦"),
        ("zh-CN", "09/23/2026"),
        ("ja-JP", "09/23/2026"),
    ],
)
def test_year_last_date_uses_the_selected_locale_order(locale, value):
    reference = date(2026, 9, 8)
    assert parse_appointment_date(value, locale, reference_date=reference) == date(2026, 9, 23)


@pytest.mark.parametrize("value", ["3/11", "3.11", "3-11", "3 11", "3/11/2026"])
def test_ambiguous_numeric_date_uses_explicit_locale_order(value):
    reference = date(2026, 1, 1)
    assert parse_appointment_date(value, "en-US", reference_date=reference) == date(2026, 3, 11)
    assert parse_appointment_date(value, "zh-CN", reference_date=reference) == date(2026, 3, 11)
    assert parse_appointment_date(value, "ja-JP", reference_date=reference) == date(2026, 3, 11)
    assert parse_appointment_date(value, "si-LK", reference_date=reference) == date(2026, 11, 3)
    assert parse_appointment_date(value, "ta-LK", reference_date=reference) == date(2026, 11, 3)
    assert parse_appointment_date(value, "hi-IN", reference_date=reference) == date(2026, 11, 3)
    assert parse_appointment_date(value, "es-ES", reference_date=reference) == date(2026, 11, 3)
    assert parse_appointment_date(value, "fr-FR", reference_date=reference) == date(2026, 11, 3)
    assert parse_appointment_date(value, "de-DE", reference_date=reference) == date(2026, 11, 3)
    assert parse_appointment_date(value, "ar-SA", reference_date=reference) == date(2026, 11, 3)


def test_iso_date_accepts_terminal_speech_punctuation():
    reference = date(2026, 9, 8)
    assert parse_appointment_date(
        "2026-09-23.", reference_date=reference
    ) == date(2026, 9, 23)


@pytest.mark.parametrize(
    "value",
    [
        "09:30",
        "9:30",
        "09 30",
        "09.30",
        "9/30",
        "9-30",
        "٠٩:٣٠",
        "०९:३०",
        "０９：３０",
    ],
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
        ("si-LK", "පෙරවරුව 11", "11:00"),
        ("si-LK", "පස්වරු හතර", "16:00"),
        ("si-LK", "පෙරවරුව අට", "08:00"),
        ("si-LK", "පෙරවරුව අටට", "08:00"),
        ("si-LK", "පස්වරු පහ", "17:00"),
        ("si-LK", "පස්වරු 4:30ට", "16:30"),
        ("ta-LK", "மாலை 4:30", "16:30"),
        ("ta-LK", "காலை ஒன்பது மணி", "09:00"),
        ("ta-LK", "மாலை நான்கு மணி", "16:00"),
        ("hi-IN", "शाम 4:30 बजे", "16:30"),
        ("hi-IN", "सुबह नौ बजे", "09:00"),
        ("hi-IN", "शाम चार बजे", "16:00"),
        ("es-ES", "4:30 de la tarde", "16:30"),
        ("es-ES", "a las nueve de la mañana", "09:00"),
        ("es-ES", "las nueve de la mañana", "09:00"),
        ("es-ES", "cuatro de la tarde", "16:00"),
        ("fr-FR", "16 h 30", "16:30"),
        ("fr-FR", "9h30", "09:30"),
        ("fr-FR", "neuf heures du matin", "09:00"),
        ("fr-FR", "quatre heures de l'après-midi", "16:00"),
        ("de-DE", "16:30 Uhr", "16:30"),
        ("de-DE", "morgens neun Uhr", "09:00"),
        ("de-DE", "nachmittags vier Uhr", "16:00"),
        ("ar-SA", "٤:٣٠ مساءً", "16:30"),
        ("ar-SA", "الساعة التاسعة صباحًا", "09:00"),
        ("ar-SA", "الساعة الرابعة مساءً", "16:00"),
        ("zh-CN", "下午4点30分", "16:30"),
        ("zh-CN", "上午九点", "09:00"),
        ("zh-CN", "下午四点", "16:00"),
        ("zh-CN", "下午四点三十分", "16:30"),
        ("ja-JP", "午後4時30分", "16:30"),
        ("ja-JP", "午前九時", "09:00"),
        ("ja-JP", "午後四時", "16:00"),
        ("ja-JP", "午後四時三十分", "16:30"),
        ("si-LK", "පෙරවරුව නවය තිහ", "09:30"),
        ("ta-LK", "காலை ஒன்பது மணி முப்பது நிமிடம்", "09:30"),
        ("hi-IN", "सुबह नौ बजकर तीस मिनट", "09:30"),
        ("es-ES", "las nueve y media de la mañana", "09:30"),
        ("fr-FR", "neuf heures trente du matin", "09:30"),
        ("de-DE", "neun Uhr dreißig morgens", "09:30"),
        ("ar-SA", "الساعة التاسعة والنصف صباحًا", "09:30"),
        ("zh-CN", "下午四点半", "16:30"),
        ("ja-JP", "午後四時半", "16:30"),
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
    "value,expected",
    [("9", "09:00"), ("9am", "09:00"), ("9 am", "09:00"), ("9.30", "09:30"), ("9/30", "09:30")],
)
def test_common_short_time_forms(value, expected):
    parsed = parse_appointment_time(value)
    assert parsed is not None
    assert parsed.strftime("%H:%M") == expected


@pytest.mark.parametrize(
    "value", ["please use 9:30", "9:30 tomorrow", "time=9/30", "9/30/45", "abc9amxyz"]
)
def test_time_parser_rejects_partial_or_extra_input(value):
    assert parse_appointment_time(value) is None


@pytest.mark.parametrize(
    "value",
    ["07:59", "17:01", "24:00", "09:60", "7 AM", "5:01 PM", "9 AM PM"],
)
def test_time_limits_still_apply(value):
    assert parse_appointment_time(value) is None


@pytest.mark.parametrize("value", ["පෙරවරුව 7:59", "පස්වරු 5:01", "පෙරවරු පස්වරු 11"])
def test_sinhala_spoken_time_limits_and_conflicts_still_apply(value):
    assert parse_appointment_time(value, "si-LK") is None


def test_sinhala_spoken_time_advances_the_booking_flow():
    manager = DialogueManager()
    session_id = str(uuid4())
    manager.start_session(session_id, "si-LK")
    saved = []

    def send(value):
        def save(payload):
            saved.append(payload)
            return _saved_booking(payload)

        return manager.process_message(session_id, "si-LK", value, lambda *_: True, save)

    assert send("හරිත් පෙරේරා").step == "specialty"
    assert send("දන්ත").step == "appointment_date"
    assert send((date.today() + timedelta(days=7)).isoformat()).step == "appointment_time"
    confirmation = send("පස්වරු හතර")
    assert confirmation.step == "confirm"
    assert "16:00" in confirmation.assistant_text
    assert send("ඔව්").status == "booked"
    assert saved[0]["appointment_time"].strftime("%H:%M") == "16:00"


def test_date_limits_and_invalid_calendar_dates_still_apply():
    assert parse_appointment_date((date.today() - timedelta(days=1)).isoformat()) is None
    assert parse_appointment_date((date.today() + timedelta(days=366)).isoformat()) is None
    assert parse_appointment_date("2026-02-30") is None


@pytest.mark.parametrize(
    "value",
    [
        "book 2026/09/23 please",
        "2026/09/23 at 9",
        "09/23/26",
        "2026/13/23",
        "32/09/2026",
    ],
)
def test_date_parser_rejects_partial_ambiguous_or_invalid_input(value):
    reference = date(2026, 9, 8)
    assert parse_appointment_date(value, reference_date=reference) is None


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
