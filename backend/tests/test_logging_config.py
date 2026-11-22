import json
import logging
import sys
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.logging_config import (
    JsonFormatter,
    TextFormatter,
    attempt_var,
    configure_logging,
    request_id_var,
)

_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


@pytest.fixture(autouse=True)
def restore_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    saved = {
        name: (list(lg.handlers), lg.level, lg.propagate, lg.disabled)
        for name in _UVICORN_LOGGERS
        for lg in [logging.getLogger(name)]
    }
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    for name, (hs, lvl, propagate, disabled) in saved.items():
        lg = logging.getLogger(name)
        lg.handlers[:] = hs
        lg.setLevel(lvl)
        lg.propagate = propagate
        lg.disabled = disabled


def _record(
    msg: str = "hello", level: int = logging.INFO, exc_info=None, **extra: object
) -> logging.LogRecord:
    record = logging.LogRecord("app.test", level, __file__, 1, msg, None, exc_info)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def _with_request_id(value: str, fn):
    token = request_id_var.set(value)
    try:
        return fn()
    finally:
        request_id_var.reset(token)


def test_json_line_has_fields_and_request_id() -> None:
    line = _with_request_id("abc123", lambda: JsonFormatter().format(_record("hello")))

    obj = json.loads(line)
    assert (obj["level"], obj["logger"], obj["msg"], obj["request_id"]) == (
        "INFO",
        "app.test",
        "hello",
        "abc123",
    )
    assert datetime.fromisoformat(obj["ts"]).utcoffset() is not None


def test_json_omits_request_id_when_unset() -> None:
    obj = json.loads(JsonFormatter().format(_record()))

    assert "request_id" not in obj


def test_json_and_text_show_the_attempt_only_when_set() -> None:
    assert "attempt" not in json.loads(JsonFormatter().format(_record()))
    assert "attempt=" not in TextFormatter().format(_record())

    token = attempt_var.set(2)
    try:
        assert json.loads(JsonFormatter().format(_record()))["attempt"] == 2
        assert TextFormatter().format(_record("hello")).endswith("hello attempt=2")
    finally:
        attempt_var.reset(token)


def test_json_includes_extra_fields() -> None:
    obj = json.loads(JsonFormatter().format(_record(service="checkout", status=202)))

    assert (obj["service"], obj["status"]) == ("checkout", 202)


def test_json_extra_cannot_overwrite_core_fields() -> None:
    obj = json.loads(JsonFormatter().format(_record("real", level=logging.ERROR, msg_id=1)))

    assert obj["msg"] == "real"
    assert obj["level"] == "ERROR"


def test_json_traceback_is_one_line_in_exc() -> None:
    try:
        raise ZeroDivisionError("boom")
    except ZeroDivisionError:
        record = _record("boom", logging.ERROR, exc_info=sys.exc_info())

    line = JsonFormatter().format(record)

    assert "\n" not in line
    assert "ZeroDivisionError" in json.loads(line)["exc"]


def test_uvicorns_color_message_extra_is_not_logged() -> None:
    record = _record("Uvicorn running", color_message="Uvicorn running on [1m%s[0m")

    assert "color_message" not in json.loads(JsonFormatter().format(record))
    assert "color_message" not in TextFormatter().format(record)


def test_text_line_shows_dash_without_request_id() -> None:
    line = TextFormatter().format(_record("hello"))

    assert line.endswith("INFO [-] app.test: hello")


def test_text_line_escapes_newlines_so_a_caller_cannot_forge_a_log_line() -> None:
    record = _record(
        "GET /x\n12:00:00 INFO [admin] app.access: GET /fake 200",
        path="/x\r\n12:00:00 INFO forged",
    )

    line = TextFormatter().format(record)

    assert "\n" not in line
    assert "\r" not in line
    assert "\\n12:00:00 INFO [admin]" in line


def test_text_traceback_stays_multiline() -> None:
    try:
        raise ZeroDivisionError("boom")
    except ZeroDivisionError:
        record = _record("failed", logging.ERROR, exc_info=sys.exc_info())

    assert TextFormatter().format(record).count("\n") > 1


def test_text_line_shows_id_and_extras() -> None:
    line = _with_request_id(
        "abc123", lambda: TextFormatter().format(_record("done", status=202))
    )

    assert "[abc123]" in line
    assert line.endswith("done status=202")


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO", "json")
    configure_logging("INFO", "json")

    ours = [h for h in logging.getLogger().handlers if getattr(h, "_app_logging", False)]
    assert len(ours) == 1


def test_configure_logging_keeps_other_handlers() -> None:
    root = logging.getLogger()
    other = logging.NullHandler()
    root.addHandler(other)

    configure_logging("INFO", "text")

    assert other in root.handlers


def test_configure_logging_sets_level_and_format() -> None:
    configure_logging("warning", "json")
    root = logging.getLogger()
    (ours,) = [h for h in root.handlers if getattr(h, "_app_logging", False)]
    assert root.level == logging.WARNING
    assert isinstance(ours.formatter, JsonFormatter)

    configure_logging("DEBUG", "text")
    (ours,) = [h for h in root.handlers if getattr(h, "_app_logging", False)]
    assert root.level == logging.DEBUG
    assert isinstance(ours.formatter, TextFormatter)


@pytest.mark.parametrize(("level", "fmt"), [("loud", "json"), ("INFO", "xml")])
def test_configure_logging_rejects_bad_values(level: str, fmt: str) -> None:
    with pytest.raises(ValueError):
        configure_logging(level, fmt)


def test_uvicorn_access_logger_is_disabled_and_error_logger_propagates() -> None:
    uv = logging.getLogger("uvicorn")
    uv.addHandler(logging.NullHandler())
    uv.propagate = False

    configure_logging("INFO", "json")

    assert logging.getLogger("uvicorn.access").disabled is True
    assert uv.handlers == []
    assert uv.propagate is True
    assert logging.getLogger("uvicorn.error").propagate is True


def test_settings_log_format_defaults_to_json() -> None:
    assert Settings(_env_file=None).log_format == "json"


def test_settings_rejects_unknown_log_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FORMAT", "xml")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
