from datetime import UTC, date, datetime, time
from uuid import uuid4

from sqlalchemy import Date, DateTime, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (UniqueConstraint("appointment_date", "appointment_time", name="uq_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid4()), index=True
    )
    patient_name: Mapped[str] = mapped_column(String(80), nullable=False)
    specialty: Mapped[str] = mapped_column(String(80), nullable=False)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False, index=True)
    language_locale: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="booked")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
