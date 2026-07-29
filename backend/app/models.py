from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LogEvent(Base):
    __tablename__ = "log_events"

    id: Mapped[int] = mapped_column(primary_key=True)
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
