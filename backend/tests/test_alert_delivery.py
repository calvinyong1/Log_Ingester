import logging
from datetime import UTC, datetime

import httpx
import pytest

from app.worker.alerts import send_alert

URL = "https://example.com/hook"
FIRED_AT = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


class Receiver:
    """Stands in for httpx.post: replays one scripted outcome per call."""

    def __init__(self, outcomes: list[int | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.posted: list[dict] = []

    def post(self, url: str, *, json: dict, timeout: float) -> httpx.Response:
        self.posted.append(json)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(outcome, request=httpx.Request("POST", url))


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr("app.worker.alerts.time.sleep", recorded.append)
    return recorded


def _send(receiver: Receiver, monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    monkeypatch.setattr("app.worker.alerts.httpx.post", receiver.post)
    kwargs: dict = {
        "alert_id": 7,
        "fired_at": FIRED_AT,
        "service": "checkout",
        "total": 5,
        "errors": 3,
        "error_rate": 0.6,
        "webhook_url": URL,
    }
    send_alert(**{**kwargs, **overrides})


def test_payload_has_content_alert_id_and_utc_fired_at(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    receiver = Receiver([204])

    _send(receiver, monkeypatch)

    (body,) = receiver.posted
    assert body["content"].startswith("[ALERT] checkout:")
    assert body["alert_id"] == 7
    parsed = datetime.fromisoformat(body["fired_at"])
    assert parsed == FIRED_AT
    assert parsed.utcoffset() is not None
    assert (body["service"], body["total"], body["errors"]) == ("checkout", 5, 3)
    assert body["error_rate"] == 0.6


def test_payload_stops_discord_from_pinging_mentions_in_the_service_name(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    receiver = Receiver([204])

    _send(receiver, monkeypatch, service="@everyone")

    (body,) = receiver.posted
    assert body["allowed_mentions"] == {"parse": []}


def test_non_2xx_is_retried_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    receiver = Receiver([500, 204])

    _send(receiver, monkeypatch)

    assert len(receiver.posted) == 2
    assert sleeps == [1]


def test_gives_up_after_max_attempts_without_raising(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float], caplog: pytest.LogCaptureFixture
) -> None:
    receiver = Receiver([500, 500, 500])

    with caplog.at_level(logging.WARNING, logger="app.worker.alerts"):
        _send(receiver, monkeypatch)

    assert len(receiver.posted) == 3
    assert sleeps == [1, 2]
    records = [r for r in caplog.records if r.name == "app.worker.alerts"]
    assert len([r for r in records if r.levelno == logging.ERROR]) == 1
    assert len([r for r in records if "Webhook attempt" in r.getMessage()]) == 2


def test_failed_attempt_warning_includes_the_status_code(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float], caplog: pytest.LogCaptureFixture
) -> None:
    receiver = Receiver([500, 204])

    with caplog.at_level(logging.WARNING, logger="app.worker.alerts"):
        _send(receiver, monkeypatch)

    (warning,) = [r for r in caplog.records if "Webhook attempt" in r.getMessage()]
    assert "1/3" in warning.getMessage()
    assert "HTTP 500" in warning.getMessage()


def test_timeout_is_retried(monkeypatch: pytest.MonkeyPatch, sleeps: list[float]) -> None:
    receiver = Receiver([httpx.ReadTimeout("t"), 204])

    _send(receiver, monkeypatch)

    assert len(receiver.posted) == 2


def test_single_attempt_does_not_sleep(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    receiver = Receiver([500])

    _send(receiver, monkeypatch, max_attempts=1)

    assert len(receiver.posted) == 1
    assert sleeps == []


def test_no_webhook_url_makes_no_request(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float], caplog: pytest.LogCaptureFixture
) -> None:
    receiver = Receiver([])

    with caplog.at_level(logging.WARNING, logger="app.worker.alerts"):
        _send(receiver, monkeypatch, webhook_url=None)

    assert receiver.posted == []
    (alert,) = [r for r in caplog.records if r.name == "app.worker.alerts"]
    assert alert.levelno == logging.WARNING
    assert alert.getMessage().startswith("[ALERT] checkout:")
    assert alert.service == "checkout"
    assert alert.alert_id == 7
