import base64
from datetime import UTC, datetime

# log_events.id is a 32-bit integer; a larger value in a hand-made cursor would
# make Postgres raise on the comparison and surface as a 500 instead of a 422.
_MAX_ID = 2**31 - 1


def encode_cursor(timestamp: datetime, event_id: int) -> str:
    """Opaque position of one event in the (timestamp, id) order.

    The client only stores and returns it, so the format can change without
    touching the frontend; it carries no secret.
    """
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    raw = f"{timestamp.astimezone(UTC).isoformat()}|{event_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    """Inverse of encode_cursor; raises ValueError for anything malformed."""
    padded = cursor + "=" * (-len(cursor) % 4)
    # validate=True: the default silently drops characters outside the alphabet.
    raw = base64.b64decode(padded.replace("-", "+").replace("_", "/"), validate=True).decode()
    timestamp_text, separator, id_text = raw.partition("|")
    if not separator:
        raise ValueError("cursor has no id")
    timestamp = datetime.fromisoformat(timestamp_text)
    event_id = int(id_text)
    if not 0 <= event_id <= _MAX_ID:
        raise ValueError("cursor id out of range")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    try:
        return timestamp.astimezone(UTC), event_id
    except OverflowError as exc:
        # An offset can push a year-1 or year-9999 timestamp out of range when it is
        # converted to UTC; OverflowError is not a ValueError, so callers would miss it.
        raise ValueError("cursor timestamp out of range") from exc
