import time
import uuid
from dataclasses import dataclass

ERROR_LEVELS = {"ERROR", "CRITICAL"}


@dataclass
class WindowCounts:
    total: int
    errors: int

    @property
    def error_rate(self) -> float:
        return self.errors / self.total if self.total else 0.0


class ErrorRateTracker:
    """Rolling per-service event/error counts backed by Redis sorted sets.

    Two ZSETs per service (`events:{service}`, `errors:{service}`) hold one
    member per processed event, scored by processing time — not the event's
    self-reported timestamp, since the window tracks recent arrival rate.
    Each `record()` call trims entries older than `window_seconds` first.
    """

    def __init__(self, redis_conn, window_seconds: int):
        self._redis = redis_conn
        self._window_seconds = window_seconds

    def record(self, service: str, level: str, now: float | None = None) -> WindowCounts:
        now = time.time() if now is None else now
        cutoff = now - self._window_seconds
        events_key = f"events:{service}"
        errors_key = f"errors:{service}"
        member = f"{now}:{uuid.uuid4().hex}"

        pipe = self._redis.pipeline()
        pipe.zadd(events_key, {member: now})
        pipe.zremrangebyscore(events_key, 0, cutoff)
        pipe.expire(events_key, self._window_seconds * 2)
        if level in ERROR_LEVELS:
            pipe.zadd(errors_key, {member: now})
        pipe.zremrangebyscore(errors_key, 0, cutoff)
        pipe.expire(errors_key, self._window_seconds * 2)
        pipe.zcard(events_key)
        pipe.zcard(errors_key)
        *_, total, errors = pipe.execute()

        return WindowCounts(total=total, errors=errors)

    def acquire_alert_cooldown(self, service: str, cooldown_seconds: int) -> bool:
        """True if an alert should fire now; False if one already fired recently."""
        key = f"alert_cooldown:{service}"
        return bool(self._redis.set(key, "1", nx=True, ex=cooldown_seconds))
