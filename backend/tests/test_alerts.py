from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Alert, LogEvent

FIRED = datetime(2026, 11, 3, 12, 0, 0, tzinfo=UTC)


async def _add(session_factory: async_sessionmaker[AsyncSession], *rows: object) -> None:
    async with session_factory() as session:
        session.add_all(rows)
        await session.commit()


def _alert(service: str = "checkout", fired_at: datetime = FIRED) -> Alert:
    return Alert(
        service=service,
        fired_at=fired_at,
        window_seconds=300,
        total=10,
        errors=8,
        error_rate=0.8,
        threshold=0.5,
    )


def _event(service: str, level: str, seconds_before: int, message: str = "m") -> LogEvent:
    at = FIRED - timedelta(seconds=seconds_before)
    return LogEvent(
        service=service, level=level, message=message, timestamp=at, received_at=at
    )


async def test_list_alerts_empty(client: AsyncClient) -> None:
    r = await client.get("/alerts")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}


async def test_list_alerts_newest_first_with_service_filter_and_paging(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _add(
        session_factory,
        _alert("checkout", FIRED - timedelta(hours=2)),
        _alert("search", FIRED - timedelta(hours=1)),
        _alert("checkout", FIRED),
    )

    body = (await client.get("/alerts")).json()
    assert body["total"] == 3
    assert [a["service"] for a in body["items"]] == ["checkout", "search", "checkout"]
    assert body["items"][0]["error_rate"] == 0.8
    assert body["items"][0]["threshold"] == 0.5

    only = (await client.get("/alerts", params={"service": "checkout"})).json()
    assert only["total"] == 2
    assert {a["service"] for a in only["items"]} == {"checkout"}

    page = (await client.get("/alerts", params={"limit": 1, "offset": 1})).json()
    assert page["total"] == 3
    assert [a["service"] for a in page["items"]] == ["search"]


async def test_alert_events_are_the_services_events_inside_the_window(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _add(
        session_factory,
        _alert(),
        _event("checkout", "ERROR", 10, "in window"),
        _event("checkout", "INFO", 299, "oldest in window"),
        _event("checkout", "ERROR", 301, "too old"),
        _event("search", "ERROR", 10, "other service"),
        LogEvent(  # after the alert fired
            service="checkout",
            level="ERROR",
            message="too new",
            timestamp=FIRED + timedelta(seconds=5),
            received_at=FIRED + timedelta(seconds=5),
        ),
    )
    alert_id = (await client.get("/alerts")).json()["items"][0]["id"]

    body = (await client.get(f"/alerts/{alert_id}/events")).json()
    assert body["total"] == 2
    assert [e["message"] for e in body["items"]] == ["in window", "oldest in window"]

    errors = (await client.get(f"/alerts/{alert_id}/events", params={"level": "ERROR"})).json()
    assert [e["message"] for e in errors["items"]] == ["in window"]


async def test_alert_events_unknown_alert_is_404(client: AsyncClient) -> None:
    r = await client.get("/alerts/999/events")
    assert r.status_code == 404


async def test_alerts_have_no_write_endpoint(client: AsyncClient) -> None:
    # The dashboard is read-only; alerts come only from the worker.
    for method in ("post", "put", "patch", "delete"):
        r = await getattr(client, method)("/alerts")
        assert r.status_code == 405
