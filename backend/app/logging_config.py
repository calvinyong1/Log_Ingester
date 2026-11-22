import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

# The id of the request being handled (or the job being run). Formatters read it
# themselves, so any record emitted in that context carries it.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Which run of the current job this is (1 = first try). Set only inside an RQ job,
# so API lines never carry it.
attempt_var: ContextVar[int | None] = ContextVar("attempt", default=None)

_MARKER = "_app_logging"

# Attributes every LogRecord has; anything else on a record came from `extra=`.
# Uvicorn's `color_message` is the same text with ANSI codes, which only its own
# formatter uses.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "color_message",
}


def _extras(record: logging.LogRecord) -> dict[str, object]:
    return {k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS}


class JsonFormatter(logging.Formatter):
    """One JSON object per line; a traceback is folded into the `exc` string."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if request_id := request_id_var.get():
            payload["request_id"] = request_id
        if (attempt := attempt_var.get()) is not None:
            payload["attempt"] = attempt
        for key, value in _extras(record).items():
            payload.setdefault(key, value)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str)


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_ESCAPES = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _one_line(value: object) -> str:
    """Escape control characters so caller-controlled text (a request path, a
    service name) can't end a text line and start a forged one. A traceback is
    app-generated and stays multi-line."""
    return _CONTROL_CHARS.sub(
        lambda m: _ESCAPES.get(m.group(), f"\\x{ord(m.group()):02x}"), str(value)
    )


class TextFormatter(logging.Formatter):
    """`HH:MM:SS LEVEL [request_id] logger: message key=value ...`, for reading locally."""

    def __init__(self) -> None:
        super().__init__(datefmt="%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        request_id = request_id_var.get() or "-"
        line = (
            f"{self.formatTime(record, self.datefmt)} {record.levelname} "
            f"[{request_id}] {record.name}: {_one_line(record.getMessage())}"
        )
        if (attempt := attempt_var.get()) is not None:
            line += f" attempt={attempt}"
        for key, value in _extras(record).items():
            line += f" {key}={_one_line(value)}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


_FORMATTERS = {"json": JsonFormatter, "text": TextFormatter}


def configure_logging(level: str, fmt: str) -> None:
    levels = logging.getLevelNamesMapping()
    name = level.upper()
    if name not in levels:
        raise ValueError(f"Unknown log level: {level!r}")
    if fmt not in _FORMATTERS:
        raise ValueError(f"Unknown log format: {fmt!r} (expected one of {sorted(_FORMATTERS)})")

    root = logging.getLogger()
    # Only drop a handler this function installed, so a second call doesn't
    # duplicate lines and a test's capture handler is left alone.
    for handler in [h for h in root.handlers if getattr(h, _MARKER, False)]:
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, _MARKER, True)
    handler.setFormatter(_FORMATTERS[fmt]())
    root.addHandler(handler)
    root.setLevel(levels[name])

    # Uvicorn installs its own handlers and levels; send its startup and error
    # lines through ours instead. Its access log is off: the request middleware
    # writes an equivalent line that also carries the request id.
    for uvicorn_name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(uvicorn_name)
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
