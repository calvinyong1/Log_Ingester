#!/usr/bin/env python3
"""Healthy steady-state traffic: DEBUG, INFO and WARNING only, no errors.

Every service stays far below the alert threshold, so this never fires an
alert. Use it to fill the dashboard with a normal baseline.

    export API_KEY=<key from .env>
    python3 demo/healthy_traffic.py --rate 5 --duration 120
"""

from _common import run

if __name__ == "__main__":
    run("Send healthy traffic (no ERROR or CRITICAL events).", lambda service: 0.0)
