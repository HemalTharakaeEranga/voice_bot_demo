import unicodedata
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time
from threading import Lock
from time import monotonic

from app.dialogue.translations import LANGUAGES
from app.dialogue.validators import (
    normalize_input,
    parse_appointment_date,
    parse_appointment_time,
    sanitize_slot_text,
)

SlotAvailabilityChecker = Callable[[date, time], bool]
BookingSaver = Callable[[dict[str, object]], dict[str, str]]
Clock = Callable[[], float]
WallClock = Callable[[], datetime]
DEFAULT_SESSION_TTL_SECONDS = 30 * 60
DEFAULT_MAX_SESSIONS = 1000


class SessionNotFoundError(LookupError):
    """Raised when a session identifier is unknown or has expired."""


@dataclass
class ConversationState:
    language_locale: str
    last_access: float
    step: str = "patient_name"
    patient_name: str | None = None
    specialty: str | None = None
    appointment_date: date | None = None
    appointment_time: time | None = None
    failure_count: int = 0
    terminal_result: "DialogueResult | None" = None


@dataclass
class DialogueResult:
    assistant_text: str
    step: str
    status: str = "active"
    booking: dict[str, str] | None = field(default=None)


class DialogueManager:
    """Deterministic, task-limited dialogue manager.

    The default demo intentionally does not use an LLM. This keeps the booking
    flow predictable, prevents prompt injection, and makes testing easier.
    """

    def __init__(
        self,
        *,
        session_ttl_seconds: float = DEFAULT_SESSION_TTL_SECONDS,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        clock: Clock = monotonic,
        wall_clock: WallClock = datetime.now,
    ) -> None:
        if session_ttl_seconds <= 0:
            raise ValueError("session_ttl_seconds must be greater than zero")
        if max_sessions <= 0:
            raise ValueError("max_sessions must be greater than zero")
        self._session_ttl_seconds = session_ttl_seconds
        self._max_sessions = max_sessions
        self._clock = clock
        self._wall_clock = wall_clock
        self._sessions: OrderedDict[str, ConversationState] = OrderedDict()
        self._lock = Lock()

    def start_session(self, session_id: str, language_locale: str) -> DialogueResult:
        language = LANGUAGES[language_locale]
        with self._lock:
            now = self._clock()
            self._prune_expired(now)
            if session_id not in self._sessions and len(self._sessions) >= self._max_sessions:
                self._sessions.popitem(last=False)
            self._sessions[session_id] = ConversationState(
                language_locale=language_locale,
                last_access=now,
            )
            self._sessions.move_to_end(session_id)
        return DialogueResult(
            assistant_text=language.prompts["greeting"],
            step="patient_name",
        )

    def process_message(
        self,
        session_id: str,
        language_locale: str,
        user_text: str,
        is_slot_available: SlotAvailabilityChecker,
        save_booking: BookingSaver,
    ) -> DialogueResult:
        with self._lock:
            now = self._clock()
            self._prune_expired(now)
            state = self._sessions.get(session_id)
            if state is None:
                raise SessionNotFoundError
            state.last_access = now
            self._sessions.move_to_end(session_id)
            if state.language_locale != language_locale:
                state.language_locale = language_locale

            language = LANGUAGES[state.language_locale]
            normalized = normalize_input(user_text).casefold()

            if state.terminal_result is not None:
                if self._contains_any(normalized, language.restart_words):
                    return self._restart(state)
                return state.terminal_result

            global_result = self._handle_global_commands(state, normalized)
            if global_result is not None:
                if global_result.status != "active":
                    state.terminal_result = global_result
                return global_result

            if state.step == "patient_name":
                state.patient_name = sanitize_slot_text(user_text)
                if len(state.patient_name) < 2:
                    return DialogueResult(language.prompts["ask_name"], state.step)
                state.step = "specialty"
                return DialogueResult(language.prompts["ask_specialty"], state.step)

            if state.step == "specialty":
                state.specialty = sanitize_slot_text(user_text)
                if len(state.specialty) < 2:
                    return DialogueResult(language.prompts["ask_specialty"], state.step)
                state.step = "appointment_date"
                return DialogueResult(language.prompts["ask_date"], state.step)

            if state.step == "appointment_date":
                parsed_date = parse_appointment_date(
                    user_text,
                    state.language_locale,
                    reference_date=self._wall_clock().date(),
                )
                if parsed_date is None:
                    state.failure_count += 1
                    return DialogueResult(language.prompts["invalid_date"], state.step)
                state.appointment_date = parsed_date
                state.failure_count = 0
                state.step = "appointment_time"
                return DialogueResult(language.prompts["ask_time"], state.step)

            if state.step == "appointment_time":
                parsed_time = parse_appointment_time(user_text, state.language_locale)
                if parsed_time is None:
                    state.failure_count += 1
                    return DialogueResult(language.prompts["invalid_time"], state.step)
                if state.appointment_date is None:
                    state.step = "appointment_date"
                    return DialogueResult(language.prompts["ask_date"], state.step)
                if not self._is_future_slot(state.appointment_date, parsed_time):
                    state.failure_count += 1
                    return DialogueResult(language.prompts["invalid_time"], state.step)
                if not is_slot_available(state.appointment_date, parsed_time):
                    return DialogueResult(language.prompts["slot_taken"], state.step)
                state.appointment_time = parsed_time
                state.failure_count = 0
                state.step = "confirm"
                return DialogueResult(self._confirmation_text(state), state.step)

            if state.step == "confirm":
                # Negation takes precedence: "no, don't book" must never book.
                if self._contains_any(normalized, language.no_words):
                    state.step = "appointment_time"
                    state.appointment_time = None
                    return DialogueResult(language.prompts["ask_time"], state.step)

                if self._contains_any(normalized, language.yes_words):
                    if state.appointment_date is None or state.appointment_time is None:
                        state.step = "appointment_date"
                        return DialogueResult(language.prompts["ask_date"], state.step)
                    if not self._is_future_slot(state.appointment_date, state.appointment_time):
                        state.step = "appointment_time"
                        state.appointment_time = None
                        return DialogueResult(language.prompts["invalid_time"], state.step)
                    if not is_slot_available(state.appointment_date, state.appointment_time):
                        state.step = "appointment_time"
                        return DialogueResult(language.prompts["slot_taken"], state.step)

                    booking_payload = {
                        "patient_name": state.patient_name or "Demo Patient",
                        "specialty": state.specialty or "General Medicine",
                        "appointment_date": state.appointment_date,
                        "appointment_time": state.appointment_time,
                        "language_locale": state.language_locale,
                    }
                    booking = save_booking(booking_payload)
                    confirmation = language.prompts["booked"].format(
                        code=booking["public_id"][-8:].upper()
                    )
                    state.step = "done"
                    state.terminal_result = DialogueResult(
                        assistant_text=confirmation,
                        step="done",
                        status="booked",
                        booking=booking,
                    )
                    return state.terminal_result

                return DialogueResult(language.prompts["not_yes_no"], state.step)

            return DialogueResult(language.prompts["task_only"], "patient_name")

    def _prune_expired(self, now: float) -> None:
        cutoff = now - self._session_ttl_seconds
        while self._sessions:
            oldest_session_id = next(iter(self._sessions))
            if self._sessions[oldest_session_id].last_access > cutoff:
                break
            self._sessions.popitem(last=False)

    def _is_future_slot(self, appointment_date: date, appointment_time: time) -> bool:
        now = self._wall_clock()
        if appointment_date != now.date():
            return appointment_date > now.date()
        return appointment_time > now.time()

    def _handle_global_commands(
        self, state: ConversationState, normalized_text: str
    ) -> DialogueResult | None:
        language = LANGUAGES[state.language_locale]

        if self._contains_any(normalized_text, language.emergency_words):
            return DialogueResult(
                language.prompts["emergency"], "transfer_requested", status="transfer_requested"
            )

        if self._contains_any(normalized_text, language.cancel_words):
            state.step = "cancelled"
            return DialogueResult(language.prompts["cancelled"], "cancelled", status="cancelled")

        if self._contains_any(normalized_text, language.human_words):
            return DialogueResult(
                language.prompts["transfer"], "transfer_requested", status="transfer_requested"
            )

        if self._contains_any(normalized_text, language.restart_words):
            return self._restart(state)

        return None

    @staticmethod
    def _contains_any(text: str, candidates: frozenset[str]) -> bool:
        def word_character(character: str) -> bool:
            # Python's \w excludes combining marks used by Sinhala, Tamil and Hindi.
            return unicodedata.category(character)[0] in "LMN" or character in "_\u200c\u200d"

        def unspaced_script(character: str) -> bool:
            return "\u3040" <= character <= "\u30ff" or "\u3400" <= character <= "\u9fff"

        for candidate in candidates:
            candidate = normalize_input(candidate).casefold()
            start = text.find(candidate)
            while start != -1:
                end = start + len(candidate)
                # Chinese and Japanese phrases do not require separating spaces.
                left_boundary = (
                    start == 0
                    or not word_character(text[start - 1])
                    or unspaced_script(candidate[0])
                )
                right_boundary = (
                    end == len(text)
                    or not word_character(text[end])
                    or unspaced_script(candidate[-1])
                )
                if left_boundary and right_boundary:
                    return True
                start = text.find(candidate, start + 1)
        return False

    @staticmethod
    def _restart(state: ConversationState) -> DialogueResult:
        state.step = "patient_name"
        state.patient_name = None
        state.specialty = None
        state.appointment_date = None
        state.appointment_time = None
        state.failure_count = 0
        state.terminal_result = None
        return DialogueResult(LANGUAGES[state.language_locale].prompts["restarted"], state.step)

    @staticmethod
    def _confirmation_text(state: ConversationState) -> str:
        language = LANGUAGES[state.language_locale]
        return language.prompts["confirm"].format(
            name=state.patient_name,
            specialty=state.specialty,
            date=state.appointment_date.isoformat() if state.appointment_date else "",
            time=state.appointment_time.strftime("%H:%M") if state.appointment_time else "",
        )
