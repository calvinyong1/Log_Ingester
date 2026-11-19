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
    # Printed rather than logged: the worker process has no logging handlers
    # configured, and Python's default "last resort" handler would otherwise
    # double up this line on stderr alongside this print on stdout.
    print(message)

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
    for attempt in range(max_attempts):
        try:
            response = httpx.post(webhook_url, json=payload, timeout=timeout_seconds)
            response.raise_for_status()
            return
        except httpx.HTTPError:
            if attempt + 1 < max_attempts:
                time.sleep(2**attempt)
            else:
                logger.exception(
                    "Failed to deliver alert webhook for %s after %d attempts",
                    service,
                    max_attempts,
                )
