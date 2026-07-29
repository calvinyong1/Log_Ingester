from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LogEventIn(BaseModel):
    service: str = Field(min_length=1, max_length=128)
    level: LogLevel
    message: str = Field(min_length=1)
    timestamp: datetime | None = None


class LogEventAccepted(BaseModel):
    """Response for POST /logs: the event has been queued, not yet persisted."""

    status: Literal["queued"] = "queued"
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
