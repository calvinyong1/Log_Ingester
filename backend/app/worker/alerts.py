import logging

import httpx

logger = logging.getLogger("app.worker.alerts")


def send_alert(
    *,
    service: str,
    total: int,
    errors: int,
    error_rate: float,
    webhook_url: str | None,
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

    try:
        httpx.post(
            webhook_url,
            json={
                "service": service,
                "total": total,
                "errors": errors,
                "error_rate": error_rate,
            },
            timeout=5.0,
        )
    except httpx.HTTPError:
        logger.exception("Failed to deliver alert webhook for %s", service)
