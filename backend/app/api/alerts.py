from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Alert, LogEvent
from app.schemas import AlertOut, AlertPage, LogEventOut, LogEventPage

# Read-only and open like GET /logs. Alerts are written only by the worker, so
# there is deliberately no write endpoint for the browser to reach.
router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertPage)
async def list_alerts(
    service: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> AlertPage:
    filters = [Alert.service == service] if service is not None else []
    items = (
        (
            await session.execute(
                select(Alert)
                .where(*filters)
                .order_by(Alert.fired_at.desc(), Alert.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    total = await session.scalar(select(func.count()).select_from(Alert).where(*filters)) or 0
    return AlertPage(items=[AlertOut.model_validate(a) for a in items], total=total)


@router.get("/{alert_id}/events", response_model=LogEventPage)
async def list_alert_events(
    alert_id: int,
    level: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> LogEventPage:
    """The service's events inside the window that tripped the alert.

    Matched on received_at, not the producer's timestamp: the worker's window
    runs on processing time, so a late or backfilled event still counted.
    """
    alert = await session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    filters = [
        LogEvent.service == alert.service,
        LogEvent.received_at >= alert.fired_at - timedelta(seconds=alert.window_seconds),
        LogEvent.received_at <= alert.fired_at,
    ]
    if level is not None:
        filters.append(LogEvent.level == level)

    base = select(LogEvent).where(*filters)
    items = (
        (
            await session.execute(
                base.order_by(LogEvent.received_at.desc(), LogEvent.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    return LogEventPage(items=[LogEventOut.model_validate(e) for e in items], total=total)
