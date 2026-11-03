#!/usr/bin/env python3
"""Realistic traffic with failures, including one service that goes down.

Most services see an occasional error. `payment-service` is failing badly
(its processor is down), which pushes its error rate past the default 50%
alert threshold once it has 5+ events in the 5 minute window, so the worker
logs an [ALERT] line. `notification-service` is flaky but stays under the
threshold, to show the dashboard distinguishing the two.

    export API_KEY=<key from .env>
    python3 demo/degraded_traffic.py --rate 5 --duration 120
    docker compose logs worker | grep ALERT
"""

from _common import run

# Probability that an event from the service is ERROR or CRITICAL.
ERROR_RATES = {
    "payment-service": 0.75,
    "notification-service": 0.20,
}
BACKGROUND_ERROR_RATE = 0.03

if __name__ == "__main__":
    run(
        "Send traffic that includes errors and one failing service.",
        lambda service: ERROR_RATES.get(service, BACKGROUND_ERROR_RATE),
    )
