import logging

import pytest
import rq

from app.config import get_settings
from app.worker.logging_worker import LoggingWorker


@pytest.fixture
def rq_loggers():
    saved = {}
    for name in ("rq.worker", "rq.job"):
        logger = logging.getLogger(name)
        saved[name] = (list(logger.handlers), logger.propagate)
    yield
    for name, (handlers, propagate) in saved.items():
        logger = logging.getLogger(name)
        logger.handlers[:] = handlers
        logger.propagate = propagate


def test_bootstrap_configures_logging_before_rq_sets_up_its_handlers(
    monkeypatch: pytest.MonkeyPatch, rq_loggers: None
) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        "app.worker.logging_worker.configure_logging",
        lambda level, fmt: calls.append(("configure", level, fmt)),
    )

    def fake_rq_bootstrap(self, logging_level="INFO", date_format="", log_format=""):
        calls.append(("rq_bootstrap", logging_level))

    monkeypatch.setattr(rq.Worker, "bootstrap", fake_rq_bootstrap)

    # Skip __init__: it would need a live Redis connection.
    worker = object.__new__(LoggingWorker)
    worker.bootstrap()

    settings = get_settings()
    assert calls == [
        ("configure", settings.log_level, settings.log_format),
        ("rq_bootstrap", settings.log_level),
    ]


def test_bootstrap_removes_the_handlers_the_rq_cli_already_installed(
    monkeypatch: pytest.MonkeyPatch, rq_loggers: None
) -> None:
    monkeypatch.setattr("app.worker.logging_worker.configure_logging", lambda level, fmt: None)
    monkeypatch.setattr(rq.Worker, "bootstrap", lambda self, **kwargs: None)
    # `rq worker` does this before any worker object exists.
    for name in ("rq.worker", "rq.job"):
        logger = logging.getLogger(name)
        logger.addHandler(logging.NullHandler())
        logger.propagate = False

    worker = object.__new__(LoggingWorker)
    worker.bootstrap()

    for name in ("rq.worker", "rq.job"):
        logger = logging.getLogger(name)
        assert logger.handlers == []
        assert logger.propagate is True
