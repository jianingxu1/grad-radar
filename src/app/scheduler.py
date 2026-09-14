"""Long-running scheduler for revision-aware GitHub ingestion."""

import logging
from contextlib import contextmanager
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.database.session import create_session_factory
from app.logging import configure_logging
from app.services.github_ingestion import IngestionSummary, ingest_all

logger = logging.getLogger(__name__)

SCHEDULER_TIMEZONE = ZoneInfo("America/Los_Angeles")
_ADVISORY_LOCK_ID = 7_421_103


@contextmanager
def ingestion_lock(session_factory: sessionmaker[Session]):
    """Acquire a database lock so only one deployed worker ingests at a time."""
    with session_factory() as session:
        acquired = session.scalar(
            text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": _ADVISORY_LOCK_ID}
        )
        try:
            yield bool(acquired)
        finally:
            if acquired:
                session.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": _ADVISORY_LOCK_ID}
                )


def run_scheduled_ingestion(
    session_factory: sessionmaker[Session], github_token: str | None
) -> list[IngestionSummary] | None:
    with ingestion_lock(session_factory) as acquired:
        if not acquired:
            logger.warning("scheduler.ingestion.skipped reason=already_running")
            return None
        return ingest_all(session_factory, github_token)


def configure_scheduler(
    scheduler: BlockingScheduler,
    session_factory: sessionmaker[Session],
    github_token: str | None,
) -> None:
    def run() -> None:
        run_scheduled_ingestion(session_factory, github_token)

    job_defaults = {
        "id": "github-ingestion",
        "replace_existing": True,
        "max_instances": 1,
        "coalesce": True,
        "misfire_grace_time": 300,
    }
    scheduler.add_job(
        run,
        trigger=CronTrigger(hour="7-20", minute="*/15", timezone=SCHEDULER_TIMEZONE),
        **job_defaults,
    )
    scheduler.add_job(
        run,
        trigger=CronTrigger(hour="1,3,5,21,23", minute="0", timezone=SCHEDULER_TIMEZONE),
        id="github-ingestion-overnight",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    scheduler = BlockingScheduler(timezone=SCHEDULER_TIMEZONE)
    configure_scheduler(scheduler, create_session_factory(settings), settings.github_token)
    logger.info("scheduler.started timezone=%s", SCHEDULER_TIMEZONE.key)
    scheduler.start()


if __name__ == "__main__":
    main()
