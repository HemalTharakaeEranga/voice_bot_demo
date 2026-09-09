import re
import unicodedata
from datetime import date, time, timedelta

YEAR_FIRST_DATE_PATTERN = re.compile(
    r"^([0-9]{4})(?:\s*[-/.]\s*|\s+)([0-9]{1,2})"
    r"(?:\s*[-/.]\s*|\s+)([0-9]{1,2})$"
)
YEAR_LAST_DATE_PATTERN = re.compile(
    r"^([0-9]{1,2})(?:\s*[-/.]\s*|\s+)([0-9]{1,2})"
    r"(?:\s*[-/.]\s*|\s+)([0-9]{4})$"
)
YEARLESS_NUMERIC_DATE_PATTERN = re.compile(
    r"^([0-9]{1,2})\s*[-/.\s]\s*([0-9]{1,2})$"
)
CJK_DATE_PATTERN = re.compile(
    r"^(?:([0-9〇零一二两三四五六七八九十]{4})\s*年\s*)?"
    r"([0-9〇零一二两三四五六七八九十]{1,3})\s*月\s*"
    r"([0-9〇零一二两三四五六七八九十]{1,3})\s*(?:日|号|號)?$"
)
TIME_PATTERN = re.compile(r"^([0-9]{1,2})(?:\s*[:./-]\s*|\s+)([0-9]{1,2})$")
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
        "من",
        "يوم",
        "بتاريخ",
    }
)

_MERIDIEM_MARKERS = {
    "en-US": (
        ("in the morning", "morning"),
        ("in the afternoon", "in the evening", "afternoon", "evening"),
    ),
    "si-LK": (
        ("පෙරවරුව", "පෙරවරු", "පෙ.ව.", "පෙ.ව"),
        ("පස්වරුව", "පස්වරු", "ප.ව.", "ප.ව"),
    ),
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
    "si-LK": ("පැයට", "විනාඩි"),
    "ta-LK": ("நிமிடங்கள்", "நிமிடம்", "மணிக்கு", "மணி"),
    "hi-IN": ("बजकर", "मिनट", "बजे"),
    "es-ES": ("a las", "a la", "las", "la", "horas", "hora", "minutos", "minuto"),
    "fr-FR": ("heures", "heure", "minutes", "minute", "à", "h"),
    "de-DE": ("minuten", "minute", "uhr", "um"),
    "ar-SA": ("الساعة", "ساعة", "دقائق", "دقيقة"),
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
_SINHALA_HOURS = {
    "එක": 1,
    "එකයි": 1,
    "දෙක": 2,
    "දෙකයි": 2,
    "තුන": 3,
    "තුනයි": 3,
    "හතර": 4,
    "හතරයි": 4,
    "පහ": 5,
    "පහයි": 5,
    "හය": 6,
    "හයයි": 6,
    "හත": 7,
    "හතයි": 7,
    "අට": 8,
    "අටයි": 8,
    "නවය": 9,
    "නවයයි": 9,
    "දහය": 10,
    "දහයයි": 10,
    "එකොළහ": 11,
    "එකොළහයි": 11,
    "එකොලහ": 11,
    "එකොලහයි": 11,
    "දොළහ": 12,
    "දොළහයි": 12,
    "දොලහ": 12,
    "දොලහයි": 12,
}
_TAMIL_HOURS = {
    "ஒன்று": 1,
    "ஒரு": 1,
    "இரண்டு": 2,
    "மூன்று": 3,
    "நான்கு": 4,
    "ஐந்து": 5,
    "ஆறு": 6,
    "ஏழு": 7,
    "எட்டு": 8,
    "ஒன்பது": 9,
    "பத்து": 10,
    "பதினொன்று": 11,
    "பன்னிரண்டு": 12,
}
_HINDI_HOURS = {
    "एक": 1,
    "दो": 2,
    "तीन": 3,
    "चार": 4,
    "पाँच": 5,
    "पांच": 5,
    "छह": 6,
    "छः": 6,
    "सात": 7,
    "आठ": 8,
    "नौ": 9,
    "दस": 10,
    "ग्यारह": 11,
    "बारह": 12,
}
_SPANISH_HOURS = {
    "uno": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
}
_FRENCH_HOURS = {
    "un": 1,
    "une": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "onze": 11,
    "douze": 12,
}
_GERMAN_HOURS = {
    "ein": 1,
    "eins": 1,
    "eine": 1,
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fünf": 5,
    "fuenf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwölf": 12,
    "zwoelf": 12,
}
_ARABIC_HOURS = {
    "واحد": 1,
    "واحدة": 1,
    "الواحدة": 1,
    "اثنان": 2,
    "اثنين": 2,
    "اثنتان": 2,
    "الثانية": 2,
    "ثلاثة": 3,
    "الثالثة": 3,
    "أربعة": 4,
    "اربعة": 4,
    "الرابعة": 4,
    "خمسة": 5,
    "الخامسة": 5,
    "ستة": 6,
    "السادسة": 6,
    "سبعة": 7,
    "السابعة": 7,
    "ثمانية": 8,
    "الثامنة": 8,
    "تسعة": 9,
    "التاسعة": 9,
    "عشرة": 10,
    "العاشرة": 10,
    "أحد عشر": 11,
    "احد عشر": 11,
    "الحادية عشرة": 11,
    "اثنا عشر": 12,
    "اثني عشر": 12,
    "الثانية عشرة": 12,
}
_SPOKEN_HOURS = {
    "si-LK": _SINHALA_HOURS,
    "ta-LK": _TAMIL_HOURS,
    "hi-IN": _HINDI_HOURS,
    "es-ES": _SPANISH_HOURS,
    "fr-FR": _FRENCH_HOURS,
    "de-DE": _GERMAN_HOURS,
    "ar-SA": _ARABIC_HOURS,
}
_SPOKEN_MINUTES = {
    locale: {word.casefold(): minute for word, minute in words.items()}
    for locale, words in {
        "si-LK": {
            "පහළොව": 15,
            "පහළොවයි": 15,
            "තිහ": 30,
            "තිහයි": 30,
            "හතළිස් පහ": 45,
        },
        "ta-LK": {"பதினைந்து": 15, "முப்பது": 30, "நாற்பத்தைந்து": 45},
        "hi-IN": {"पंद्रह": 15, "तीस": 30, "पैंतालीस": 45},
        "es-ES": {
            "cuarto": 15,
            "y cuarto": 15,
            "quince": 15,
            "media": 30,
            "y media": 30,
            "treinta": 30,
            "cuarenta y cinco": 45,
        },
        "fr-FR": {
            "quart": 15,
            "et quart": 15,
            "quinze": 15,
            "demie": 30,
            "et demie": 30,
            "trente": 30,
            "quarante cinq": 45,
        },
        "de-DE": {"viertel": 15, "fünfzehn": 15, "dreißig": 30, "fünfundvierzig": 45},
        "ar-SA": {
            "ربع": 15,
            "والربع": 15,
            "خمسة عشر": 15,
            "نصف": 30,
            "النصف": 30,
            "والنصف": 30,
            "ثلاثون": 30,
            "خمسة وأربعون": 45,
        },
    }.items()
}

_ENGLISH_ORDINAL_ONES = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
}
_ENGLISH_ORDINAL_TENS = {"twentieth": 20, "thirtieth": 30}


def _indexed_number_words(first_value: int, words: tuple[str, ...]) -> dict[str, int]:
    return {word: first_value + offset for offset, word in enumerate(words)}


_SINHALA_DAY_WORDS = _indexed_number_words(
    13,
    (
        "දහතුන",
        "දහහතර",
        "පහළොව",
        "දහසය",
        "දහහත",
        "දහඅට",
        "දහනවය",
        "විස්ස",
        "විසි එක",
        "විසි දෙක",
        "විසි තුන",
        "විසි හතර",
        "විසි පහ",
        "විසි හය",
        "විසි හත",
        "විසි අට",
        "විසි නවය",
        "තිහ",
        "තිස් එක",
    ),
) | {
    "දාහතර": 14,
    "දාසය": 16,
    "දාහත": 17,
    "දහනමය": 19,
    "විසි නමය": 29,
}

_TAMIL_DAY_WORDS = _indexed_number_words(
    13,
    (
        "பதின்மூன்று",
        "பதினான்கு",
        "பதினைந்து",
        "பதினாறு",
        "பதினேழு",
        "பதினெட்டு",
        "பத்தொன்பது",
        "இருபது",
        "இருபத்தொன்று",
        "இருபத்திரண்டு",
        "இருபத்துமூன்று",
        "இருபத்துநான்கு",
        "இருபத்தைந்து",
        "இருபத்தாறு",
        "இருபத்தேழு",
        "இருபத்தெட்டு",
        "இருபத்தொன்பது",
        "முப்பது",
        "முப்பத்தொன்று",
    ),
) | {
    "இருபத்தி ஒன்று": 21,
    "இருபத்தி இரண்டு": 22,
    "இருபத்தி மூன்று": 23,
    "இருபத்து மூன்று": 23,
    "இருபத்தி நான்கு": 24,
    "இருபத்தி ஐந்து": 25,
    "இருபத்தி ஆறு": 26,
    "இருபத்தி ஏழு": 27,
    "இருபத்தி எட்டு": 28,
    "இருபத்தி ஒன்பது": 29,
    "முப்பத்தி ஒன்று": 31,
}

_HINDI_DAY_WORDS = _indexed_number_words(
    13,
    (
        "तेरह",
        "चौदह",
        "पंद्रह",
        "सोलह",
        "सत्रह",
        "अठारह",
        "उन्नीस",
        "बीस",
        "इक्कीस",
        "बाईस",
        "तेईस",
        "चौबीस",
        "पच्चीस",
        "छब्बीस",
        "सत्ताईस",
        "अट्ठाईस",
        "उनतीस",
        "तीस",
        "इकतीस",
    ),
) | {"पन्द्रह": 15}

_SPANISH_DAY_WORDS = _indexed_number_words(
    13,
    (
        "trece",
        "catorce",
        "quince",
        "dieciséis",
        "diecisiete",
        "dieciocho",
        "diecinueve",
        "veinte",
        "veintiuno",
        "veintidós",
        "veintitrés",
        "veinticuatro",
        "veinticinco",
        "veintiséis",
        "veintisiete",
        "veintiocho",
        "veintinueve",
        "treinta",
        "treinta y uno",
    ),
) | {
    "dieciseis": 16,
    "veintiún": 21,
    "veintiun": 21,
    "veintidos": 22,
    "veintitres": 23,
    "veintiseis": 26,
}

_FRENCH_DAY_WORDS = _indexed_number_words(
    13,
    (
        "treize",
        "quatorze",
        "quinze",
        "seize",
        "dix sept",
        "dix huit",
        "dix neuf",
        "vingt",
        "vingt et un",
        "vingt deux",
        "vingt trois",
        "vingt quatre",
        "vingt cinq",
        "vingt six",
        "vingt sept",
        "vingt huit",
        "vingt neuf",
        "trente",
        "trente et un",
    ),
)

_GERMAN_CARDINAL_DAYS = _indexed_number_words(
    13,
    (
        "dreizehn",
        "vierzehn",
        "fünfzehn",
        "sechzehn",
        "siebzehn",
        "achtzehn",
        "neunzehn",
        "zwanzig",
        "einundzwanzig",
        "zweiundzwanzig",
        "dreiundzwanzig",
        "vierundzwanzig",
        "fünfundzwanzig",
        "sechsundzwanzig",
        "siebenundzwanzig",
        "achtundzwanzig",
        "neunundzwanzig",
        "dreißig",
        "einunddreißig",
    ),
)
_GERMAN_ORDINAL_DAYS = _indexed_number_words(
    1,
    (
        "erste",
        "zweite",
        "dritte",
        "vierte",
        "fünfte",
        "sechste",
        "siebte",
        "achte",
        "neunte",
        "zehnte",
        "elfte",
        "zwölfte",
        "dreizehnte",
        "vierzehnte",
        "fünfzehnte",
        "sechzehnte",
        "siebzehnte",
        "achtzehnte",
        "neunzehnte",
        "zwanzigste",
        "einundzwanzigste",
        "zweiundzwanzigste",
        "dreiundzwanzigste",
        "vierundzwanzigste",
        "fünfundzwanzigste",
        "sechsundzwanzigste",
        "siebenundzwanzigste",
        "achtundzwanzigste",
        "neunundzwanzigste",
        "dreißigste",
        "einunddreißigste",
    ),
)
_GERMAN_DAY_WORDS = (
    _GERMAN_CARDINAL_DAYS
    | _GERMAN_ORDINAL_DAYS
    | {f"{word}n": day for word, day in _GERMAN_ORDINAL_DAYS.items()}
    | {f"{word}r": day for word, day in _GERMAN_ORDINAL_DAYS.items()}
)

_ARABIC_CARDINAL_DAYS = _indexed_number_words(
    13,
    (
        "ثلاثة عشر",
        "أربعة عشر",
        "خمسة عشر",
        "ستة عشر",
        "سبعة عشر",
        "ثمانية عشر",
        "تسعة عشر",
        "عشرون",
        "واحد وعشرون",
        "اثنان وعشرون",
        "ثلاثة وعشرون",
        "أربعة وعشرون",
        "خمسة وعشرون",
        "ستة وعشرون",
        "سبعة وعشرون",
        "ثمانية وعشرون",
        "تسعة وعشرون",
        "ثلاثون",
        "واحد وثلاثون",
    ),
)
_ARABIC_ORDINAL_DAYS = _indexed_number_words(
    1,
    (
        "الأول",
        "الثاني",
        "الثالث",
        "الرابع",
        "الخامس",
        "السادس",
        "السابع",
        "الثامن",
        "التاسع",
        "العاشر",
        "الحادي عشر",
        "الثاني عشر",
        "الثالث عشر",
        "الرابع عشر",
        "الخامس عشر",
        "السادس عشر",
        "السابع عشر",
        "الثامن عشر",
        "التاسع عشر",
        "العشرون",
        "الحادي والعشرون",
        "الثاني والعشرون",
        "الثالث والعشرون",
        "الرابع والعشرون",
        "الخامس والعشرون",
        "السادس والعشرون",
        "السابع والعشرون",
        "الثامن والعشرون",
        "التاسع والعشرون",
        "الثلاثون",
        "الحادي والثلاثون",
    ),
)
_ARABIC_DAY_WORDS = (
    _ARABIC_CARDINAL_DAYS
    | _ARABIC_ORDINAL_DAYS
    | {
        word.replace("ون", "ين"): day
        for word, day in (_ARABIC_CARDINAL_DAYS | _ARABIC_ORDINAL_DAYS).items()
        if "ون" in word
    }
    | {"الثالثة والعشرون": 23}
)

_LOCALIZED_DAY_WORDS = {
    locale: {word.casefold(): day for word, day in words.items()}
    for locale, words in {
        "si-LK": _SINHALA_DAY_WORDS,
        "ta-LK": _TAMIL_DAY_WORDS,
        "hi-IN": _HINDI_DAY_WORDS,
        "es-ES": _SPANISH_DAY_WORDS,
        "fr-FR": _FRENCH_DAY_WORDS,
        "de-DE": _GERMAN_DAY_WORDS,
        "ar-SA": _ARABIC_DAY_WORDS,
    }.items()
}
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


def _build_numeric_booking_date(
    first: int,
    second: int,
    year: int | None,
    language_locale: str,
    today: date,
) -> date | None:
    """Resolve a two-part date without guessing across locale conventions."""
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
    return _build_booking_date(month, day, year, today)


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


def _parse_natural_date(value: str, language_locale: str, today: date) -> date | None:
    natural = value.casefold().replace("’", "'")
    natural = re.sub(r"[,،，.?!]+", " ", natural)
    natural = natural.replace("'", " ").replace("-", " ")
    tokens = natural.split()
    month_indexes = [index for index, token in enumerate(tokens) if token in MONTH_NAME_TO_NUMBER]
    if not month_indexes:
        return None

    candidates: list[date] = []
    for month_index in month_indexes:
        month = MONTH_NAME_TO_NUMBER[tokens[month_index]]
        day_numbers: list[int] = []
        day_words: list[str] = []
        year: int | None = None
        for index, token in enumerate(tokens):
            if index == month_index or token in DATE_FILLER_WORDS:
                continue
            ordinal = re.fullmatch(r"([0-9]{1,4})(st|nd|rd|th|e|º|ª)?", token)
            if ordinal is None:
                day_words.append(token)
                continue
            number = int(ordinal.group(1))
            if number >= 1000 and ordinal.group(2) is None and year is None:
                year = number
            else:
                day_numbers.append(number)

        if day_numbers and day_words:
            continue
        if len(day_numbers) == 1:
            day = day_numbers[0]
        elif not day_numbers and day_words:
            day = _parse_spoken_day(day_words, language_locale)
        else:
            continue
        if day is None:
            continue
        parsed = _build_booking_date(month, day, year, today)
        if parsed is not None:
            candidates.append(parsed)

    return candidates[0] if len(candidates) == 1 else None


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

    match = YEAR_FIRST_DATE_PATTERN.fullmatch(structured_value)
    if match:
        try:
            parsed = date(*(int(part) for part in match.groups()))
        except ValueError:
            return None
        return _date_in_booking_window(parsed, today)

    year_last_match = YEAR_LAST_DATE_PATTERN.fullmatch(structured_value)
    if year_last_match:
        first, second, year = (int(part) for part in year_last_match.groups())
        return _build_numeric_booking_date(first, second, year, language_locale, today)

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
        return _build_numeric_booking_date(first, second, None, language_locale, today)

    return _parse_natural_date(value, language_locale, today)


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
            elif language_locale == "ar-SA" and len(marker) == 1:
                # Arabic م/ص abbreviations may touch a digit, but must not be
                # removed from a full Arabic word such as الخامسة.
                updated, count = re.subn(
                    rf"(?<![^\W\d_]){re.escape(marker)}(?![^\W\d_])", " ", value
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


def _parse_english_ordinal(words: list[str]) -> int | None:
    if len(words) == 1:
        return _ENGLISH_ORDINAL_ONES.get(words[0], _ENGLISH_ORDINAL_TENS.get(words[0]))
    if (
        len(words) == 2
        and words[0] in _ENGLISH_TENS
        and words[1] in _ENGLISH_ORDINAL_ONES
        and _ENGLISH_ORDINAL_ONES[words[1]] < 10
    ):
        return _ENGLISH_TENS[words[0]] + _ENGLISH_ORDINAL_ONES[words[1]]
    return None


def _parse_spoken_day(words: list[str], language_locale: str) -> int | None:
    phrase = " ".join(words)
    if language_locale == "en-US":
        return _parse_english_number(words) or _parse_english_ordinal(words)
    localized_hour = _SPOKEN_HOURS.get(language_locale, {}).get(phrase)
    if localized_hour is not None:
        return localized_hour
    return _LOCALIZED_DAY_WORDS.get(language_locale, {}).get(phrase)


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


def _parse_localized_time_words(value: str, language_locale: str) -> tuple[int, int] | None:
    hours = _SPOKEN_HOURS[language_locale]
    hour = hours.get(value)
    if hour is not None:
        return hour, 0
    words = value.split()
    for split_at in range(1, len(words)):
        hour = hours.get(" ".join(words[:split_at]))
        minute_phrase = " ".join(words[split_at:])
        minute = int(minute_phrase) if minute_phrase.isdecimal() else None
        if minute is None:
            minute = _SPOKEN_MINUTES.get(language_locale, {}).get(minute_phrase)
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
    if language_locale in _SPOKEN_HOURS:
        return _parse_localized_time_words(value, language_locale)
    if language_locale == "en-US":
        return _parse_english_time_words(value)
    if language_locale in {"zh-CN", "ja-JP"}:
        parts = value.split()
        if len(parts) not in {1, 2}:
            return None
        hour = _parse_cjk_number(parts[0])
        minute = _parse_cjk_number(parts[1]) if len(parts) == 2 else 0
        return (hour, minute) if hour is not None and minute is not None else None
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

    if language_locale in {"zh-CN", "ja-JP"}:
        value = value.replace("半", " 30 ")
    if language_locale == "fr-FR":
        value = re.sub(r"(?<=\d)\s*h\s*(?=\d)", ":", value)
        value = re.sub(r"(?<=\d)\s*h\s*$", "", value)
    for filler in sorted(_TIME_FILLERS.get(language_locale, ()), key=len, reverse=True):
        if filler.isascii() and filler.isalpha():
            value = _replace_ascii_word(value, filler, " ")
        else:
            value = value.replace(filler, " ")
    if language_locale == "si-LK" and value.endswith("ට"):
        # Sinhala commonly appends ට to a spoken time. Strip one suffix only when
        # the remaining text is already a valid clock expression, preserving අට.
        without_suffix = " ".join(value[:-1].split())
        if _parse_clock_parts(without_suffix, language_locale) is not None:
            value = without_suffix
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
