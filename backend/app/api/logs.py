from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, status
from rq import Queue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.db import get_session
from app.models import LogEvent
from app.queue import get_queue
from app.schemas import (
    HistogramBucket,
    LogEventAccepted,
    LogEventIn,
    LogEventOut,
    LogEventPage,
    LogHistogram,
)
from app.sql import bucket_index

router = APIRouter(prefix="/logs", tags=["logs"])

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
MIN_HISTOGRAM_SPAN = timedelta(seconds=60)


def _as_utc(value: datetime) -> datetime:
    # SQLite hands back naive datetimes and clients may send them; Postgres
    # timestamptz values are already aware. Treat naive as UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


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
    timestamp = payload.timestamp or datetime.now(UTC)
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


@router.get("/services", response_model=list[str])
async def list_services(session: AsyncSession = Depends(get_session)) -> list[str]:
    result = await session.execute(
        select(LogEvent.service).distinct().order_by(LogEvent.service)
    )
    return list(result.scalars().all())


@router.get("/histogram", response_model=LogHistogram)
async def log_histogram(
    service: str | None = None,
    level: str | None = None,
    start: datetime | None = Query(None, description="Inclusive lower bound on timestamp"),
    end: datetime | None = Query(None, description="Exclusive upper bound on timestamp"),
    buckets: int = Query(24, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> LogHistogram:
    filters = []
    if service is not None:
        filters.append(LogEvent.service == service)
    if level is not None:
        filters.append(LogEvent.level == level)

    end = _as_utc(end) if end else datetime.now(UTC)
    if start is None:
        earliest = await session.scalar(
            select(func.min(LogEvent.timestamp)).where(*filters, LogEvent.timestamp < end)
        )
        start = _as_utc(earliest) if earliest else end - MIN_HISTOGRAM_SPAN
    else:
        start = _as_utc(start)

    # Avoids zero-width buckets when everything falls on one instant.
    span = max(end - start, MIN_HISTOGRAM_SPAN)
    end = start + span
    width = span.total_seconds() / buckets

    idx = bucket_index(LogEvent.timestamp, start.timestamp(), width)
    # Group via a subquery: Postgres won't match a GROUP BY expression to the
    # SELECT one when each copy carries its own bind parameters.
    binned = (
        select(idx.label("bucket"), LogEvent.level.label("level"))
        .where(*filters, LogEvent.timestamp >= start, LogEvent.timestamp < end)
        .subquery()
    )
    rows = await session.execute(
        select(binned.c.bucket, binned.c.level, func.count()).group_by(
            binned.c.bucket, binned.c.level
        )
    )

    counts = [dict.fromkeys(LEVELS, 0) for _ in range(buckets)]
    total = 0
    for bucket, row_level, n in rows:
        if row_level not in LEVELS:
            continue
        # Clamp guards float rounding right at the last boundary.
        counts[min(max(bucket, 0), buckets - 1)][row_level] += n
        total += n

    return LogHistogram(
        buckets=[
            HistogramBucket(
                start=start + timedelta(seconds=width * i),
                end=start + timedelta(seconds=width * (i + 1)),
                counts=counts[i],
            )
            for i in range(buckets)
        ],
        total=total,
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
