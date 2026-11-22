import logging
import time
from datetime import datetime

import httpx

logger = logging.getLogger("app.worker.alerts")


def send_alert(
    *,
    alert_id: int,
    fired_at: datetime,
    service: str,
    total: int,
    errors: int,
    error_rate: float,
    webhook_url: str | None,
    max_attempts: int = 3,
    timeout_seconds: float = 5.0,
) -> None:
    message = (
        f"[ALERT] {service}: error rate {error_rate:.0%} "
        f"({errors}/{total} events) exceeds threshold"
    )
    # The message keeps the "[ALERT]" prefix so `docker compose logs | grep ALERT` works
    # in both log formats.
    logger.warning(
        message,
        extra={"service": service, "alert_id": alert_id, "error_rate": error_rate},
    )

    if not webhook_url:
        return

    # "content" is what Discord requires; the rest is for receivers that parse
    # the alert, which can de-duplicate a retried delivery on alert_id.
    payload = {
        "content": message,
        # The service name is caller-supplied; without this Discord would turn
        # "@everyone" in it into a ping.
        "allowed_mentions": {"parse": []},
        "alert_id": alert_id,
        "fired_at": fired_at.isoformat(),
        "service": service,
        "total": total,
        "errors": errors,
        "error_rate": error_rate,
    }
    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.post(webhook_url, json=payload, timeout=timeout_seconds)
            response.raise_for_status()
            return
        except httpx.HTTPError as exc:
            if attempt < max_attempts:
                logger.warning(
                    "Webhook attempt %d/%d failed for %s: %s",
                    attempt,
                    max_attempts,
                    service,
                    _describe(exc),
                )
                time.sleep(2 ** (attempt - 1))
            else:
                logger.exception(
                    "Failed to deliver alert webhook for %s after %d attempts",
                    service,
                    max_attempts,
                )


def _describe(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__
