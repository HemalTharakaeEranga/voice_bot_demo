from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dialogue.manager import DialogueManager, SessionNotFoundError
from app.repository import SlotUnavailableError, create_appointment, is_slot_available
from app.schemas import (
    MessageRequest,
    MessageResponse,
    StartSessionRequest,
    StartSessionResponse,
)

router = APIRouter(prefix="/api")
dialogue_manager = DialogueManager()


@router.post("/sessions", response_model=StartSessionResponse)
def start_session(request: StartSessionRequest) -> StartSessionResponse:
    session_id = str(uuid4())
    result = dialogue_manager.start_session(session_id, request.language_locale)
    return StartSessionResponse(
        session_id=session_id,
        assistant_text=result.assistant_text,
        step=result.step,
    )


@router.post("/messages", response_model=MessageResponse)
def send_message(
    request: MessageRequest,
    database_session: Annotated[Session, Depends(get_db)],
) -> MessageResponse:
    try:
        session_uuid = UUID(request.session_id)
        if session_uuid.version != 4 or str(session_uuid) != request.session_id:
            raise ValueError
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session identifier") from exc

    def availability_checker(appointment_date, appointment_time):
        return is_slot_available(database_session, appointment_date, appointment_time)

    def booking_saver(payload):
        try:
            return create_appointment(database_session, payload)
        except SlotUnavailableError as exc:
            raise HTTPException(
                status_code=409,
                detail="Appointment slot is no longer available",
            ) from exc

    try:
        result = dialogue_manager.process_message(
            session_id=request.session_id,
            language_locale=request.language_locale,
            user_text=request.text,
            is_slot_available=availability_checker,
            save_booking=booking_saver,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found or expired") from exc

    return MessageResponse(
        assistant_text=result.assistant_text,
        step=result.step,
        status=result.status,
        booking=result.booking,
    )
