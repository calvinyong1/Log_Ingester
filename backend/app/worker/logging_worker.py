import logging

from rq import Worker
from rq.defaults import DEFAULT_LOGGING_DATE_FORMAT, DEFAULT_LOGGING_FORMAT

from app.config import get_settings
from app.logging_config import configure_logging

# RQ forks a child for every job and resolves the job function inside it, so
# anything the parent hasn't imported is imported again per job: ~1.2s of
# SQLAlchemy, asyncpg and httpx against ~30ms of real work. Importing the tasks
# here, before any fork, lets every child inherit them. This only creates the DB
# engine object; no connection is opened until a job uses it, so forking is safe.
from app.worker import tasks as _preload_job_modules  # noqa: F401
from app.worker.prune import ensure_prune_scheduled

logger = logging.getLogger(__name__)


class LoggingWorker(Worker):
    """An RQ worker whose own log lines use the app's format.

    `rq worker` installs its handlers on the `rq.worker` and `rq.job` loggers (and
    stops them propagating) before any worker object exists, so they have to be
    removed here; with none left, RQ's later setup sees the root handler and leaves
    them alone. Selected with
    `rq worker --worker-class app.worker.logging_worker.LoggingWorker`.
    """

    def bootstrap(
        self,
        logging_level: str | None = "INFO",
        date_format: str = DEFAULT_LOGGING_DATE_FORMAT,
        log_format: str = DEFAULT_LOGGING_FORMAT,
    ) -> None:
        settings = get_settings()
        configure_logging(settings.log_level, settings.log_format)
        for name in ("rq.worker", "rq.job"):
            rq_logger = logging.getLogger(name)
            rq_logger.handlers.clear()
            rq_logger.propagate = True
        # RQ's own --logging_level would otherwise pin its loggers to INFO.
        super().bootstrap(
            logging_level=settings.log_level, date_format=date_format, log_format=log_format
        )
        # Start the retention prune chain. The worker is where the job runs, and
        # it already runs with --with-scheduler. Never block startup on it.
        try:
            ensure_prune_scheduled()
        except Exception:
            logger.warning("Could not schedule the retention prune", exc_info=True)
