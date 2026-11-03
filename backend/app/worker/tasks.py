from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.db import SessionLocal
from app.models import LogEvent
from app.queue import get_redis_connection
from app.worker.alerts import send_alert
from app.worker.rate_limiter import ErrorRateTracker


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
        service=payload["service"],
        level=payload["level"],
        message=payload["message"],
        timestamp=datetime.fromisoformat(payload["timestamp"]),
    )
    async with session_factory() as session: # Create a new  AsyncSession object
        session.add(event) # Add the LogEvent to the session
        await session.commit() # Commit the log event to Postgres

    tracker = ErrorRateTracker(redis_conn, window_seconds=settings.error_rate_window_seconds)
    counts = tracker.record(event.service, event.level)

    if counts.total < settings.error_rate_min_events:
        return
    if counts.error_rate < settings.error_rate_threshold:
        return
    if not tracker.acquire_alert_cooldown(event.service, settings.alert_cooldown_seconds):
        return

    send_alert(
        service=event.service,
        total=counts.total,
        errors=counts.errors,
        error_rate=counts.error_rate,
        webhook_url=settings.alert_webhook_url,
    )
