"""Shared pieces for the demo traffic generators.

Standard library only, so the scripts run anywhere with Python 3.10+ and no
install step. Events are sent without a `timestamp`, so the API stamps them
with the current time and they land in the dashboard's recent ranges.
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable

# A small e-commerce platform: (traffic weight, one message template per level).
# Weights are relative, so the gateway sees most events.
SERVICES: dict[str, tuple[int, dict[str, str]]] = {
    "api-gateway": (35, {
        "DEBUG": "route matched for request {req}",
        "INFO": "GET /orders 200 in {ms}ms",
        "WARNING": "upstream slow: {ms}ms",
        "ERROR": "upstream returned 502 for request {req}",
        "CRITICAL": "all upstreams unhealthy",
    }),
    "auth-service": (20, {
        "DEBUG": "token cache hit for user {user}",
        "INFO": "login ok for user {user}",
        "WARNING": "failed login attempt for user {user}",
        "ERROR": "could not sign token for user {user}",
        "CRITICAL": "signing key unavailable",
    }),
    "order-service": (20, {
        "DEBUG": "order {order} state pending -> confirmed",
        "INFO": "order {order} created for user {user}",
        "WARNING": "order {order} awaiting payment for {ms}ms",
        "ERROR": "failed to persist order {order}",
        "CRITICAL": "order write path unavailable",
    }),
    "payment-service": (15, {
        "DEBUG": "payment routed to processor for order {order}",
        "INFO": "payment captured for order {order}",
        "WARNING": "processor latency high: {ms}ms",
        "ERROR": "payment declined for order {order}: processor unavailable",
        "CRITICAL": "payment processor down",
    }),
    "notification-service": (10, {
        "DEBUG": "email template rendered",
        "INFO": "email sent to user {user}",
        "WARNING": "email provider throttling, backing off {ms}ms",
        "ERROR": "failed to send email to user {user}: smtp 451",
        "CRITICAL": "notification queue not draining",
    }),
}


def _fields(rng: random.Random) -> dict:
    return {
        "ms": rng.randint(4, 900),
        "user": f"u_{rng.randint(1000, 9999)}",
        "order": f"ord_{rng.randint(10000, 99999)}",
        "req": f"req_{rng.randint(100000, 999999)}",
    }


def pick_level(rng: random.Random, error_rate: float) -> str:
    """Mostly INFO, some DEBUG/WARNING, and errors at `error_rate`."""
    if rng.random() < error_rate:
        return "CRITICAL" if rng.random() < 0.15 else "ERROR"
    return rng.choices(["DEBUG", "INFO", "WARNING"], weights=[15, 70, 15])[0]


def build_event(rng: random.Random, service: str, error_rate: float) -> dict:
    level = pick_level(rng, error_rate)
    template = SERVICES[service][1][level]
    return {"service": service, "level": level, "message": template.format(**_fields(rng))}


def post_event(url: str, api_key: str, event: dict) -> None:
    req = urllib.request.Request(
        f"{url.rstrip('/')}/logs",
        data=json.dumps(event).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        resp.read()


def run(description: str, error_rates: Callable[[str], float]) -> None:
    """Parse CLI args and send events until the duration ends or Ctrl-C.

    `error_rates(service)` is the probability that an event from that service
    is ERROR or CRITICAL; the two entry scripts differ only in this function.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--url", default=os.environ.get("API_URL", "http://localhost:8000"))
    parser.add_argument("--rate", type=float, default=5.0, help="events per second (default 5)")
    parser.add_argument(
        "--duration", type=float, default=0, help="seconds to run, 0 = until Ctrl-C"
    )
    parser.add_argument("--seed", type=int, default=None, help="seed for reproducible output")
    args = parser.parse_args()

    api_key = os.environ.get("API_KEY")
    if not api_key:
        sys.exit("API_KEY is not set. Export the key from your .env file first.")
    if args.rate <= 0:
        sys.exit("--rate must be positive")

    rng = random.Random(args.seed)
    names = list(SERVICES)
    weights = [SERVICES[n][0] for n in names]
    sent: Counter[str] = Counter()
    consecutive_failures = 0
    deadline = time.monotonic() + args.duration if args.duration else None

    print(f"Sending ~{args.rate:g} events/s to {args.url} (Ctrl-C to stop)")
    try:
        while deadline is None or time.monotonic() < deadline:
            service = rng.choices(names, weights=weights)[0]
            event = build_event(rng, service, error_rates(service))
            try:
                post_event(args.url, api_key, event)
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    sys.exit("API rejected the key (401). Check API_KEY matches the server.")
                consecutive_failures += 1
                print(f"warn: HTTP {exc.code} for {service}", file=sys.stderr)
            except (urllib.error.URLError, TimeoutError) as exc:
                consecutive_failures += 1
                print(f"warn: {exc}", file=sys.stderr)
            else:
                consecutive_failures = 0
                sent[event["level"]] += 1
            if consecutive_failures >= 10:
                sys.exit("Giving up after 10 consecutive failures. Is the API running?")
            # Jitter keeps the stream from looking metronomic on the chart.
            time.sleep(rng.expovariate(args.rate))
    except KeyboardInterrupt:
        pass

    total = sum(sent.values())
    breakdown = ", ".join(f"{lvl}={sent[lvl]}" for lvl in sorted(sent))
    print(f"\nSent {total} events ({breakdown or 'none'})")
