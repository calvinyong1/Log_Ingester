from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from rq import Queue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.db import get_session
from app.models import LogEvent
from app.queue import get_queue
from app.schemas import LogEventAccepted, LogEventIn, LogEventOut, LogEventPage

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post(
    "",
    response_model=LogEventAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
)
async def ingest_log(
    payload: LogEventIn,
    queue: Queue = Depends(get_queue),
) -> LogEventAccepted:
    timestamp = payload.timestamp or datetime.now(timezone.utc)
    queue.enqueue(
        "app.worker.tasks.process_log_event",
        {
            "service": payload.service,
            "level": payload.level,
            "message": payload.message,
            "timestamp": timestamp.isoformat(),
        },
    )
    return LogEventAccepted(
        service=payload.service,
        level=payload.level,
        message=payload.message,
        timestamp=timestamp,
    )


@router.get("", response_model=LogEventPage)
async def list_logs(
    service: str | None = None,
    level: str | None = None,
    start: datetime | None = Query(None, description="Inclusive lower bound on timestamp"),
    end: datetime | None = Query(None, description="Exclusive upper bound on timestamp"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> LogEventPage:
    filters = []
    if service is not None:
        filters.append(LogEvent.service == service)
    if level is not None:
        filters.append(LogEvent.level == level)
    if start is not None:
        filters.append(LogEvent.timestamp >= start)
    if end is not None:
        filters.append(LogEvent.timestamp < end)

    base = select(LogEvent).where(*filters)
    items = (
        await session.execute(
            base.order_by(LogEvent.timestamp.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0

    return LogEventPage(
        items=[LogEventOut.model_validate(e) for e in items],
        total=total,
    )
