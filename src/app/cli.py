import argparse
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.database.session import create_session_factory, transaction
from app.logging import configure_logging
from app.services.github_ingestion import IngestionSummary, ingest_all
from app.services.notifications import deliver_pending
from app.services.telegram import TelegramClient
from app.sources.bootstrap import bootstrap_sources

logger = logging.getLogger(__name__)


def ingest_and_deliver(
    session_factory: sessionmaker[Session],
    github_token: str | None,
    telegram_bot_token: str | None,
) -> list[IngestionSummary]:
    summaries = ingest_all(session_factory, github_token)
    with (
        session_factory.begin() as session,
        TelegramClient(telegram_bot_token) as telegram,
    ):
        delivered = deliver_pending(session, telegram, datetime.now(UTC))
    logger.info(
        "worker.ingest.completed sources=%s notifications_delivered=%s",
        len(summaries),
        delivered,
    )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap-sources", "ingest"))
    command = parser.parse_args().command
    settings = get_settings()
    configure_logging(settings.log_level)
    session_factory = create_session_factory(settings)
    if command == "ingest":
        summaries = ingest_and_deliver(
            session_factory, settings.github_token, settings.telegram_bot_token
        )
        if all(summary.status == "failed" for summary in summaries):
            raise SystemExit(1)
        return
    with transaction(session_factory) as session:
        created = bootstrap_sources(session)
    print(f"bootstrapped sources (created={created})")


if __name__ == "__main__":
    main()
