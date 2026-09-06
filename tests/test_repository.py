from datetime import date, time
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.repository import create_appointment


def _payload() -> dict[str, object]:
    return {
        "patient_name": "Demo Patient",
        "specialty": "Dental",
        "appointment_date": date(2026, 9, 10),
        "appointment_time": time(10, 30),
        "language_locale": "en-US",
    }


def test_unexpected_database_error_rolls_back_and_is_not_relabelled_as_a_slot_conflict():
    database_session = Mock(spec=Session)
    error = SQLAlchemyError("private database detail")
    database_session.flush.side_effect = error

    with pytest.raises(SQLAlchemyError) as raised:
        create_appointment(database_session, _payload())

    assert raised.value is error
    database_session.rollback.assert_called_once_with()
    database_session.commit.assert_not_called()


def test_unrelated_integrity_error_rolls_back_and_keeps_its_original_type():
    database_session = Mock(spec=Session)
    error = IntegrityError("insert", {}, Exception("different unique constraint"))
    database_session.flush.side_effect = error

    with pytest.raises(IntegrityError) as raised:
        create_appointment(database_session, _payload())

    assert raised.value is error
    database_session.rollback.assert_called_once_with()
    database_session.commit.assert_not_called()
