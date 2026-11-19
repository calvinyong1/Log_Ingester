from rq import Worker
from rq.defaults import DEFAULT_LOGGING_DATE_FORMAT, DEFAULT_LOGGING_FORMAT

from app.config import get_settings
from app.logging_config import configure_logging


class LoggingWorker(Worker):
    """An RQ worker whose own log lines use the app's format.

    RQ only installs its handlers when no ancestor logger has one, so configuring
    the root logger first makes RQ's lines (and the forked job's) flow through it.
    Selected with `rq worker --worker-class app.worker.logging_worker.LoggingWorker`.
    """

    def bootstrap(
        self,
        logging_level: str | None = "INFO",
        date_format: str = DEFAULT_LOGGING_DATE_FORMAT,
        log_format: str = DEFAULT_LOGGING_FORMAT,
    ) -> None:
        settings = get_settings()
        configure_logging(settings.log_level, settings.log_format)
        # RQ's own --logging_level would otherwise pin its loggers to INFO.
        super().bootstrap(
            logging_level=settings.log_level, date_format=date_format, log_format=log_format
        )
