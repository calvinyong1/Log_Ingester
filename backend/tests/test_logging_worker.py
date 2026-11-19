import rq

from app.config import get_settings
from app.worker.logging_worker import LoggingWorker


def test_bootstrap_configures_logging_before_rq_sets_up_its_handlers(monkeypatch) -> None:
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
