from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import get_settings

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


MAX_MESSAGE_LENGTH = 8192


class LogEventIn(BaseModel):
    service: str = Field(min_length=1, max_length=128)
    level: LogLevel
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    timestamp: datetime | None = None
    # Lets a producer safely resend an event; the server generates one if absent.
    event_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:-]{1,64}$")

    @field_validator("timestamp")
    @classmethod
    def _plausible_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        settings = get_settings()
        aware = value if value.tzinfo else value.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if aware > now + timedelta(seconds=settings.timestamp_max_future_seconds):
            raise ValueError("timestamp is too far in the future")
        if aware < now - timedelta(days=settings.timestamp_max_age_days):
            raise ValueError("timestamp is too old")
        return value


class LogEventAccepted(BaseModel):
    """Response for POST /logs: the event has been queued, not yet persisted."""

    status: Literal["queued"] = "queued"
    event_id: str
    service: str
    level: LogLevel
    message: str
    timestamp: datetime


class LogEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    level: str
    message: str
    timestamp: datetime
    received_at: datetime


class LogEventPage(BaseModel):
    items: list[LogEventOut]
    total: int


class ServiceErrorRate(BaseModel):
    service: str
    total: int
    errors: int
    error_rate: float


class ServiceErrorRates(BaseModel):
    window_seconds: int
    threshold: float
    min_events: int
    services: list[ServiceErrorRate]


class HistogramBucket(BaseModel):
    start: datetime
    end: datetime
    counts: dict[LogLevel, int]


class LogHistogram(BaseModel):
    buckets: list[HistogramBucket]
    total: int


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    fired_at: datetime
    window_seconds: int
    total: int
    errors: int
    error_rate: float
    threshold: float


class AlertPage(BaseModel):
    items: list[AlertOut]
    total: int
