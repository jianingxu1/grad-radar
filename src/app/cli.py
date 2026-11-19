import argparse
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.database.session import create_session_factory, transaction
from app.logging import configure_logging
from app.services.board_ingestion import ingest_all_boards
from app.services.github_ingestion import IngestionSummary, ingest_all
from app.services.notifications import deliver_pending
from app.services.telegram import TelegramClient
from app.sources.bootstrap import bootstrap_sources
from app.sources.seed_boards import bootstrap_seed_boards

logger = logging.getLogger(__name__)


def run_ingestion(
    session_factory: sessionmaker[Session],
    github_token: str | None,
) -> list[IngestionSummary]:
    logger.info("Preparing ingestion worker")
    with session_factory.begin() as session:
        bootstrap_seed_boards(session)
    logger.info("Running GitHub source ingestion")
    summaries = ingest_all(session_factory, github_token)
    logger.info("Running company board ingestion")
    board_results = ingest_all_boards(session_factory)
    summaries.extend(IngestionSummary(source=name, status=status) for name, status in board_results)
    logger.info("Ingestion worker finished: %s sources processed", len(summaries))
    return summaries


def run_notification_delivery(
    session_factory: sessionmaker[Session], telegram_bot_token: str
) -> int:
    logger.info("Delivering pending Telegram notifications")
    with (
        session_factory.begin() as session,
        TelegramClient(telegram_bot_token) as telegram,
    ):
        delivered = deliver_pending(session, telegram, datetime.now(UTC))
    logger.info("Telegram delivery worker finished: %s notifications delivered", delivered)
    return delivered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap-sources", "ingest", "deliver-notifications"))
    command = parser.parse_args().command
    settings = get_settings()
    configure_logging(settings.log_level)
    if command == "deliver-notifications" and not settings.telegram_bot_token:
        parser.error("TELEGRAM_BOT_TOKEN is required for deliver-notifications")
    session_factory = create_session_factory(settings)
    try:
        if command == "ingest":
            summaries = run_ingestion(session_factory, settings.github_token)
            if all(summary.status == "failed" for summary in summaries):
                raise SystemExit(1)
            return
        if command == "deliver-notifications":
            assert settings.telegram_bot_token is not None
            run_notification_delivery(session_factory, settings.telegram_bot_token)
            return
        with transaction(session_factory) as session:
            created = bootstrap_sources(session) + bootstrap_seed_boards(session)
        print(f"bootstrapped sources (created={created})")
    finally:
        session_factory.kw["bind"].dispose()


if __name__ == "__main__":
    main()
