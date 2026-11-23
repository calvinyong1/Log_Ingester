import base64
from datetime import UTC, datetime

import pytest

from app.pagination import decode_cursor, encode_cursor


def test_cursor_round_trips_timestamp_and_id() -> None:
    timestamp = datetime(2026, 4, 25, 12, 30, 15, 123456, tzinfo=UTC)

    assert decode_cursor(encode_cursor(timestamp, 9123)) == (timestamp, 9123)


def test_naive_timestamp_is_read_as_utc() -> None:
    # SQLite hands back naive datetimes; Postgres timestamptz values are aware.
    naive = datetime(2026, 4, 25, 12, 30, 15)

    decoded, _ = decode_cursor(encode_cursor(naive, 1))

    assert decoded == naive.replace(tzinfo=UTC)


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "!!!",
        "bm9uc2Vuc2U",  # base64 of "nonsense"
        "MjAyNi0wMS0wMVQwMDowMDowMCswMDowMHxhYmM",  # "2026-01-01T00:00:00+00:00|abc"
        "x" * 10_000,
    ],
)
def test_decode_rejects_malformed_cursors(cursor: str) -> None:
    with pytest.raises(ValueError):
        decode_cursor(cursor)


def test_decode_rejects_an_id_beyond_the_32_bit_column() -> None:
    # log_events.id is an INTEGER; a bigger value would make Postgres raise.
    raw = "2026-01-01T00:00:00+00:00|99999999999"
    cursor = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    with pytest.raises(ValueError):
        decode_cursor(cursor)
