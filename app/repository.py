from datetime import date, time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Appointment


class SlotUnavailableError(RuntimeError):
    """Raised when the database rejects an already occupied appointment slot."""


def _is_slot_conflict(error: IntegrityError) -> bool:
    constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if constraint_name is not None:
        return constraint_name == "uq_slot"
    return (
        "UNIQUE constraint failed: appointments.appointment_date, "
        "appointments.appointment_time"
    ) in str(error.orig)


def is_slot_available(
    database_session: Session, appointment_date: date, appointment_time: time
) -> bool:
    statement = select(Appointment.id).where(
        Appointment.appointment_date == appointment_date,
        Appointment.appointment_time == appointment_time,
        Appointment.status == "booked",
    )
    return database_session.execute(statement).scalar_one_or_none() is None


def create_appointment(database_session: Session, payload: dict[str, object]) -> dict[str, str]:
    appointment = Appointment(**payload)
    database_session.add(appointment)
    try:
        # Flush first so generated values and constraint failures are known
        # before the transaction is committed and the response is assembled.
        database_session.flush()
        result = {
            "public_id": appointment.public_id,
            "patient_name": appointment.patient_name,
            "specialty": appointment.specialty,
            "appointment_date": appointment.appointment_date.isoformat(),
            "appointment_time": appointment.appointment_time.strftime("%H:%M"),
            "language_locale": appointment.language_locale,
        }
        database_session.commit()
    except IntegrityError as exc:
        database_session.rollback()
        if _is_slot_conflict(exc):
            raise SlotUnavailableError from exc
        raise
    except SQLAlchemyError:
        database_session.rollback()
        raise

    return result
