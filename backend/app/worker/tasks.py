import logging
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.db import SessionLocal
from app.models import Alert, LogEvent
from app.queue import get_redis_connection
from app.worker.alerts import send_alert
from app.worker.rate_limiter import ErrorRateTracker

logger = logging.getLogger("app.worker.tasks")


async def process_log_event(
    payload: dict,
    *,
    session_factory: async_sessionmaker | None = None,
    redis_conn=None,
) -> None:
    # Enqueued by dotted path as a coroutine function: RQ (>=2.10) runs it with
    # asyncio.run() per job, which is only safe under the forking `rq worker`.
    settings = get_settings()
    session_factory = session_factory or SessionLocal
    redis_conn = redis_conn or get_redis_connection()

    event = LogEvent(
        event_id=payload.get("event_id"),
        service=payload["service"],
        level=payload["level"],
        message=payload["message"],
        timestamp=datetime.fromisoformat(payload["timestamp"]),
    )
    try:
        async with session_factory() as session:
            session.add(event)
            await session.commit()
    except IntegrityError:
        # Only event_id is unique: this job was redelivered after its row was
        # saved. Skip the insert but carry on, since the Redis step may be what
        # failed last time.
        if event.event_id is None:
            raise
        logger.info("Event %s already stored; skipping insert", event.event_id)

    tracker = ErrorRateTracker(redis_conn, window_seconds=settings.error_rate_window_seconds)
    counts = tracker.record(event.service, event.level, event_id=event.event_id)

    if counts.total < settings.error_rate_min_events:
        return
    if counts.error_rate < settings.error_rate_threshold:
        return
    if not tracker.acquire_alert_cooldown(event.service, settings.alert_cooldown_seconds):
        return

    # Saved before notifying so the dashboard can show the incident, but a
    # failed insert must never swallow a real alert: log it and carry on.
    try:
        async with session_factory() as session:
            session.add(
                Alert(
                    service=event.service,
                    fired_at=datetime.now(UTC),
                    window_seconds=settings.error_rate_window_seconds,
                    total=counts.total,
                    errors=counts.errors,
                    error_rate=counts.error_rate,
                    threshold=settings.error_rate_threshold,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to record alert for %s", event.service)

    send_alert(
        service=event.service,
        total=counts.total,
        errors=counts.errors,
        error_rate=counts.error_rate,
        webhook_url=settings.alert_webhook_url,
    )
