from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LogEvent(Base):
    __tablename__ = "log_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Dedupes redelivered jobs; nullable for rows written before it existed.
    event_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    service: Mapped[str] = mapped_column(String(128), index=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    message: Mapped[str] = mapped_column(Text)
    # Event time as reported by the producer (server fills if missing).
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_log_events_service_level_ts", "service", "level", "timestamp"),
    )


class Alert(Base):
    """One row per fired alert (the cooldown allows one per service per period).

    Stores the numbers that tripped it, not copies of the events: log_events is
    append-only, so the events behind an alert are recovered from the window
    [fired_at - window_seconds, fired_at] on received_at.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    service: Mapped[str] = mapped_column(String(128))
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_seconds: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    errors: Mapped[int] = mapped_column(Integer)
    error_rate: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)

    __table_args__ = (Index("ix_alerts_service_fired_at", "service", "fired_at"),)
