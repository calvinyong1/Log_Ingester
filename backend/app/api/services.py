import redis
from fastapi import APIRouter, Depends

from app.config import get_settings
from app.queue import get_redis_connection
from app.schemas import ServiceErrorRate, ServiceErrorRates

router = APIRouter(prefix="/services", tags=["services"])

EVENTS_PREFIX = "events:"


@router.get("/error-rates", response_model=ServiceErrorRates)
def get_error_rates(
    redis_conn: redis.Redis = Depends(get_redis_connection),
) -> ServiceErrorRates:
    # Sync handler on purpose: the redis client is blocking, so FastAPI runs
    # this in its threadpool instead of stalling the event loop.
    settings = get_settings()
    # Read-only snapshot of the worker's window. The worker only trims a
    # service's sets when that service logs, so quiet services can be stale.
    services = []
    for raw_key in redis_conn.scan_iter(match=f"{EVENTS_PREFIX}*"):
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        service = key.removeprefix(EVENTS_PREFIX)
        total = redis_conn.zcard(key)
        errors = redis_conn.zcard(f"errors:{service}")
        services.append(
            ServiceErrorRate(
                service=service,
                total=total,
                errors=errors,
                error_rate=round(errors / total, 4) if total else 0.0,
            )
        )
    services.sort(key=lambda s: s.service)

    return ServiceErrorRates(
        window_seconds=settings.error_rate_window_seconds,
        threshold=settings.error_rate_threshold,
        min_events=settings.error_rate_min_events,
        services=services,
    )
