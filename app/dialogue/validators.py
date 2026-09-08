import re
import unicodedata
from datetime import date, time, timedelta

DATE_PATTERN = re.compile(r"^([0-9]{4})[-/\s]([0-9]{1,2})[-/\s]([0-9]{1,2})$")
YEARLESS_NUMERIC_DATE_PATTERN = re.compile(
    r"^([0-9]{1,2})\s*[-/.\s]\s*([0-9]{1,2})$"
)
CJK_DATE_PATTERN = re.compile(
    r"^(?:([0-9〇零一二两三四五六七八九十]{4})\s*年\s*)?"
    r"([0-9〇零一二两三四五六七八九十]{1,3})\s*月\s*"
    r"([0-9〇零一二两三四五六七八九十]{1,3})\s*(?:日|号|號)?$"
)
TIME_PATTERN = re.compile(r"^([0-9]{1,2})(?:\s*[:.]\s*|\s+)([0-9]{1,2})$")
HOUR_PATTERN = re.compile(r"^([0-9]{1,2})$")
COMPACT_TIME_PATTERN = re.compile(r"^([0-9]{1,2})([0-9]{2})$")
MAX_TEMPORAL_INPUT_LENGTH = 80
MONTH_FIRST_LOCALES = frozenset({"en-US", "zh-CN", "ja-JP"})

_MONTH_NAMES = (
    (
        1,
        (
            "january",
            "jan",
            "ජනවාරි",
            "ஜனவரி",
            "जनवरी",
            "enero",
            "ene",
            "janvier",
            "janv",
            "januar",
            "يناير",
        ),
    ),
    (
        2,
        (
            "february",
            "feb",
            "පෙබරවාරි",
            "பிப்ரவரி",
            "फ़रवरी",
            "फरवरी",
            "febrero",
            "février",
            "fevrier",
            "févr",
            "fevr",
            "februar",
            "فبراير",
        ),
    ),
    (
        3,
        (
            "march",
            "mar",
            "මාර්තු",
            "மார்ச்",
            "मार्च",
            "marzo",
            "mars",
            "märz",
            "maerz",
            "mär",
            "mrz",
            "مارس",
        ),
    ),
    (
        4,
        (
            "april",
            "apr",
            "අප්‍රේල්",
            "ஏப்ரல்",
            "अप्रैल",
            "abril",
            "abr",
            "avril",
            "avr",
            "أبريل",
            "ابريل",
        ),
    ),
    (5, ("may", "මැයි", "மே", "मई", "mayo", "mai", "مايو")),
    (6, ("june", "jun", "ජූනි", "ஜூன்", "जून", "junio", "juin", "juni", "يونيو")),
    (
        7,
        (
            "july",
            "jul",
            "ජූලි",
            "ஜூலை",
            "जुलाई",
            "julio",
            "juillet",
            "juil",
            "juli",
            "يوليو",
        ),
    ),
    (
        8,
        (
            "august",
            "aug",
            "අගෝස්තු",
            "ஆகஸ்ட்",
            "अगस्त",
            "agosto",
            "ago",
            "août",
            "aout",
            "أغسطس",
            "اغسطس",
        ),
    ),
    (
        9,
        (
            "september",
            "sep",
            "sept",
            "septembre",
            "සැප්තැම්බර්",
            "செப்டம்பர்",
            "सितंबर",
            "सितम्बर",
            "septiembre",
            "setiembre",
            "سبتمبر",
        ),
    ),
    (
        10,
        (
            "october",
            "oct",
            "ඔක්තෝබර්",
            "அக்டோபர்",
            "अक्टूबर",
            "octubre",
            "octobre",
            "oktober",
            "okt",
            "أكتوبر",
            "اكتوبر",
        ),
    ),
    (
        11,
        (
            "november",
            "nov",
            "නොවැම්බර්",
            "நவம்பர்",
            "नवंबर",
            "नवम्बर",
            "noviembre",
            "novembre",
            "نوفمبر",
        ),
    ),
    (
        12,
        (
            "december",
            "dec",
            "දෙසැම්බර්",
            "டிசம்பர்",
            "दिसंबर",
            "दिसम्बर",
            "diciembre",
            "dic",
            "décembre",
            "decembre",
            "déc",
            "dezember",
            "dez",
            "ديسمبر",
        ),
    ),
)
MONTH_NAME_TO_NUMBER = {
    unicodedata.normalize("NFKC", name).casefold(): month
    for month, names in _MONTH_NAMES
    for name in names
}
DATE_FILLER_WORDS = frozenset(
    {
        "on",
        "the",
        "of",
        "please",
        "දින",
        "වන",
        "වැනි",
        "කරුණාකර",
        "ஆம்",
        "தேதி",
        "அன்று",
        "को",
        "तारीख",
        "दिन",
        "el",
        "de",
        "del",
        "le",
        "d",
        "du",
        "am",
        "den",
        "der",
        "في",
        "يوم",
        "بتاريخ",
    }
)

_MERIDIEM_MARKERS = {
    "en-US": (
        ("in the morning", "morning"),
        ("in the afternoon", "in the evening", "afternoon", "evening"),
    ),
    "si-LK": (("පෙ.ව.", "පෙ.ව"), ("ප.ව.", "ප.ව")),
    "ta-LK": (("முற்பகல்", "காலை"), ("பிற்பகல்", "மாலை")),
    "hi-IN": (("पूर्वाह्न", "सुबह"), ("अपराह्न", "दोपहर", "शाम")),
    "es-ES": (("de la mañana",), ("de la tarde", "de la noche")),
    "fr-FR": (("du matin",), ("de l'après-midi", "de l’apres-midi", "du soir")),
    "de-DE": (("vormittags", "morgens"), ("nachmittags", "abends")),
    "ar-SA": (("صباحًا", "صباحا", "ص"), ("مساءً", "مساء", "م")),
    "zh-CN": (("上午", "早上"), ("下午", "晚上")),
    "ja-JP": (("午前",), ("午後",)),
}
_TIME_FILLERS = {
    "en-US": ("o'clock", "oclock", "at"),
    "si-LK": ("පැයට", "ට"),
    "ta-LK": ("மணிக்கு", "மணி"),
    "hi-IN": ("बजे",),
    "es-ES": ("a las", "a la", "horas", "hora"),
    "fr-FR": ("heures", "heure", "à", "h"),
    "de-DE": ("uhr", "um"),
    "ar-SA": ("الساعة", "ساعة"),
    "zh-CN": ("点", "點", "时", "時", "分"),
    "ja-JP": ("時", "分", "に"),
}
_ENGLISH_ONES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_ENGLISH_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
_CJK_DIGITS = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


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


def _date_in_booking_window(parsed: date, today: date) -> date | None:
    if parsed < today or parsed > today + timedelta(days=365):
        return None
    return parsed


def _build_booking_date(month: int, day: int, year: int | None, today: date) -> date | None:
    years = (year,) if year is not None else (today.year, today.year + 1)
    for candidate_year in years:
        try:
            parsed = date(candidate_year, month, day)
        except ValueError:
            continue
        if _date_in_booking_window(parsed, today) is not None:
            return parsed
    return None


def _parse_cjk_number(value: str) -> int | None:
    if value.isdecimal():
        return int(value)
    if "十" in value:
        if value.count("十") != 1:
            return None
        tens_text, ones_text = value.split("十")
        tens = 1 if not tens_text else _CJK_DIGITS.get(tens_text)
        ones = 0 if not ones_text else _CJK_DIGITS.get(ones_text)
        if tens is None or ones is None:
            return None
        return tens * 10 + ones
    digits = [_CJK_DIGITS.get(character) for character in value]
    if not digits or any(digit is None for digit in digits):
        return None
    return int("".join(str(digit) for digit in digits))


def _parse_natural_date(value: str, today: date) -> date | None:
    natural = value.casefold().replace("’", "'")
    natural = re.sub(r"[,،，.?!]+", " ", natural)
    natural = natural.replace("'", " ").replace("-", " ")
    tokens = natural.split()
    month_indexes = [index for index, token in enumerate(tokens) if token in MONTH_NAME_TO_NUMBER]
    if len(month_indexes) != 1:
        return None

    month_index = month_indexes[0]
    month = MONTH_NAME_TO_NUMBER[tokens[month_index]]
    numbers: list[int] = []
    for index, token in enumerate(tokens):
        if index == month_index or token in DATE_FILLER_WORDS:
            continue
        ordinal = re.fullmatch(r"([0-9]{1,4})(?:st|nd|rd|th|e|º|ª)?", token)
        if ordinal is None:
            return None
        numbers.append(int(ordinal.group(1)))

    if len(numbers) == 1:
        return _build_booking_date(month, numbers[0], None, today)
    if len(numbers) == 2:
        years = [number for number in numbers if number >= 1000]
        days = [number for number in numbers if number < 1000]
        if len(years) == 1 and len(days) == 1:
            return _build_booking_date(month, days[0], years[0], today)
    return None


def parse_appointment_date(
    raw_value: str,
    language_locale: str = "en-US",
    *,
    reference_date: date | None = None,
) -> date | None:
    value = _normalize_number_input(raw_value)
    if not value or len(value) > MAX_TEMPORAL_INPUT_LENGTH:
        return None
    today = reference_date or date.today()
    structured_value = value.rstrip(" ,،，.?!")

    match = DATE_PATTERN.fullmatch(structured_value)
    if match:
        try:
            parsed = date(*(int(part) for part in match.groups()))
        except ValueError:
            return None
        return _date_in_booking_window(parsed, today)

    cjk_match = CJK_DATE_PATTERN.fullmatch(structured_value)
    if cjk_match:
        raw_year, raw_month, raw_day = cjk_match.groups()
        year = _parse_cjk_number(raw_year) if raw_year else None
        month = _parse_cjk_number(raw_month)
        day = _parse_cjk_number(raw_day)
        if month is None or day is None or (raw_year and year is None):
            return None
        return _build_booking_date(month, day, year, today)

    numeric_match = YEARLESS_NUMERIC_DATE_PATTERN.fullmatch(structured_value)
    if numeric_match:
        first, second = (int(part) for part in numeric_match.groups())
        if first > 31 or second > 31 or (first > 12 and second > 12):
            return None
        if second > 12:
            month, day = first, second
        elif first > 12:
            month, day = second, first
        elif language_locale in MONTH_FIRST_LOCALES:
            month, day = first, second
        else:
            month, day = second, first
        return _build_booking_date(month, day, None, today)

    return _parse_natural_date(value, today)


def _replace_ascii_word(value: str, word: str, replacement: str) -> str:
    return re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", replacement, value)


def _extract_meridiem(value: str, language_locale: str) -> tuple[str, str | None] | None:
    generic_am = ("a.m.", "a.m", "am")
    generic_pm = ("p.m.", "p.m", "pm")
    localized_am, localized_pm = _MERIDIEM_MARKERS.get(language_locale, ((), ()))
    found: set[str] = set()
    marker_groups = (("am", (*localized_am, *generic_am)), ("pm", (*localized_pm, *generic_pm)))
    for kind, markers in marker_groups:
        for marker in sorted(set(markers), key=len, reverse=True):
            if marker.isascii() and marker.isalpha():
                updated, count = re.subn(
                    rf"(?<![A-Za-z]){re.escape(marker)}(?![A-Za-z])", " ", value
                )
            else:
                count = value.count(marker)
                updated = value.replace(marker, " ")
            if count:
                found.add(kind)
                value = updated
    if len(found) > 1:
        return None
    return value, next(iter(found), None)


def _parse_english_number(words: list[str]) -> int | None:
    if len(words) == 1:
        return _ENGLISH_ONES.get(words[0], _ENGLISH_TENS.get(words[0]))
    if len(words) == 2 and words[0] in _ENGLISH_TENS and words[1] in _ENGLISH_ONES:
        ones = _ENGLISH_ONES[words[1]]
        if ones < 10:
            return _ENGLISH_TENS[words[0]] + ones
    return None


def _parse_english_time_words(value: str) -> tuple[int, int] | None:
    words = value.replace("-", " ").split()
    if len(words) == 3 and words[0] in {"half", "quarter"} and words[1] in {"past", "to"}:
        hour = _parse_english_number(words[2:])
        if hour is None or not 1 <= hour <= 12:
            return None
        if words[1] == "past":
            return hour, 30 if words[0] == "half" else 15
        return (hour - 1) % 12, 30 if words[0] == "half" else 45

    hour = _parse_english_number(words)
    if hour is not None:
        return hour, 0
    for split_at in range(1, len(words)):
        hour = _parse_english_number(words[:split_at])
        minute_words = words[split_at:]
        if minute_words[:1] == ["oh"]:
            minute_words = minute_words[1:]
        minute = _parse_english_number(minute_words)
        if hour is not None and minute is not None:
            return hour, minute
    return None


def _parse_clock_parts(value: str, language_locale: str) -> tuple[int, int] | None:
    match = TIME_PATTERN.fullmatch(value)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = HOUR_PATTERN.fullmatch(value)
    if match:
        return int(match.group(1)), 0
    match = COMPACT_TIME_PATTERN.fullmatch(value)
    if match:
        return int(match.group(1)), int(match.group(2))
    if language_locale == "en-US":
        return _parse_english_time_words(value)
    return None


def parse_appointment_time(raw_value: str, language_locale: str = "en-US") -> time | None:
    value = _normalize_number_input(raw_value).casefold().replace("’", "'")
    if not value or len(value) > MAX_TEMPORAL_INPUT_LENGTH:
        return None
    value = value.strip(" ,،，?!")
    meridiem_result = _extract_meridiem(value, language_locale)
    if meridiem_result is None:
        return None
    value, meridiem = meridiem_result

    if language_locale == "fr-FR":
        value = re.sub(r"(?<=\d)\s*h\s*(?=\d)", ":", value)
        value = re.sub(r"(?<=\d)\s*h\s*$", "", value)
    for filler in sorted(_TIME_FILLERS.get(language_locale, ()), key=len, reverse=True):
        if filler.isascii() and filler.isalpha():
            value = _replace_ascii_word(value, filler, " ")
        else:
            value = value.replace(filler, " ")
    value = " ".join(value.split()).strip(" .")
    parsed_parts = _parse_clock_parts(value, language_locale)
    if parsed_parts is None:
        return None
    hour, minute = parsed_parts

    if meridiem is not None:
        if not 1 <= hour <= 12:
            return None
        if meridiem == "am":
            hour = 0 if hour == 12 else hour
        elif hour != 12:
            hour += 12
    try:
        parsed = time(hour, minute)
    except ValueError:
        return None

    if parsed < time(8, 0) or parsed > time(17, 0):
        return None
    return parsed


def sanitize_slot_text(raw_value: str, max_length: int = 80) -> str:
    cleaned = " ".join(raw_value.strip().split())
    return cleaned[:max_length]
