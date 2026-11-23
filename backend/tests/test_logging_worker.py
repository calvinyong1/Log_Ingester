import logging
import subprocess
import sys
from unittest import mock

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


@pytest.fixture(autouse=True)
def prune_scheduling(monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
    # The real one needs Redis; bootstrap tests are about logging.
    stub = mock.MagicMock()
    monkeypatch.setattr("app.worker.logging_worker.ensure_prune_scheduled", stub)
    return stub


def test_bootstrap_configures_logging_before_rq_sets_up_its_handlers(
    monkeypatch: pytest.MonkeyPatch, rq_loggers: None, prune_scheduling: mock.MagicMock
) -> None:
    calls: list[tuple] = []
    prune_scheduling.side_effect = lambda: calls.append(("prune_scheduled",))
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
        ("prune_scheduled",),
    ]


def test_a_failure_scheduling_the_prune_does_not_stop_the_worker(
    monkeypatch: pytest.MonkeyPatch,
    rq_loggers: None,
    prune_scheduling: mock.MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr("app.worker.logging_worker.configure_logging", lambda level, fmt: None)
    monkeypatch.setattr(rq.Worker, "bootstrap", lambda self, **kwargs: None)
    prune_scheduling.side_effect = RuntimeError("redis down")

    object.__new__(LoggingWorker).bootstrap()

    assert "Could not schedule the retention prune" in caplog.text


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


def test_loading_the_worker_class_preloads_the_job_modules() -> None:
    # RQ forks a child per job, and a module the parent hasn't imported is
    # imported again in every child (~1.2s of SQLAlchemy, asyncpg and httpx per
    # job, against ~30ms of real work). A fresh interpreter is needed because
    # the test process has already imported them.
    code = (
        "import sys; import app.worker.logging_worker; "
        "missing = [m for m in ('app.worker.tasks', 'sqlalchemy', 'asyncpg', 'httpx') "
        "if m not in sys.modules]; "
        "print(','.join(missing))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == ""
