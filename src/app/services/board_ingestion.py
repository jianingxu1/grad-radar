"""Ingest configured public company boards independently."""

import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast

import httpx
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from app.database.models import JobPostingSource, Source
from app.repositories.job_postings import persist_postings_with_new_ids
from app.services.notifications import enqueue_new_jobs
from app.sources.ats import BoardJob, Platform, fetch_board
from app.sources.board_filter import DEFAULT_FILTER, normalize_board_jobs, validate_filter

logger = logging.getLogger(__name__)


def ingest_all_boards(session_factory: sessionmaker[Session]) -> list[tuple[str, str]]:
    with session_factory() as session:
        names = session.scalars(
            select(Source.name).where(Source.enabled, Source.platform != "github")
        ).all()
    results: list[tuple[str, str]] = []
    logger.info("Starting company board ingestion for %s sources", len(names))
    with httpx.Client(timeout=20) as client:
        for name in names:
            results.append((name, ingest_board(session_factory, client, name)))
    return results


def ingest_board(
    session_factory: sessionmaker[Session], client: httpx.Client, source_name: str
) -> str:
    started_at = perf_counter()
    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.name == source_name))
        if source is None or not source.enabled or source.platform == "github":
            raise ValueError("unknown or disabled board source")
        platform = source.platform
        board_name = source.board_name
        company_name = source.company_name
        config = source.filter_config or DEFAULT_FILTER
        platform_config = source.platform_config
    if not board_name or not company_name:
        raise ValueError("board source is missing its name or company")
    try:
        logger.info("Fetching jobs from %s board %s", platform, board_name)
        jobs = _fetch_with_retries(client, platform, board_name, platform_config)
        logger.info("Filtering %s fetched jobs from source %s", len(jobs), source_name)
        postings = normalize_board_jobs(jobs, source_name, validate_filter(config), company_name)
        checked_at = datetime.now(UTC)
        with session_factory.begin() as session:
            source = session.scalar(select(Source).where(Source.name == source_name))
            if source is None or not source.enabled:
                raise ValueError("board source was disabled during sync")
            stored_jobs, new_ids = persist_postings_with_new_ids(session, postings, checked_at)
            active_ids = {job.id for job in stored_jobs}
            deactivate = update(JobPostingSource).where(JobPostingSource.source_id == source.id)
            if active_ids:
                deactivate = deactivate.where(JobPostingSource.job_posting_id.not_in(active_ids))
            deactivated = (
                cast(CursorResult[Any], session.execute(deactivate.values(active=False))).rowcount
                or 0
            )
            notifications_enqueued = 0
            if source.initial_sync_completed:
                notifications_enqueued = enqueue_new_jobs(session, new_ids, checked_at)
            source.initial_sync_completed = True
            source.last_successful_sync_at = checked_at
            source.last_sync_status = "success"
            source.last_sync_error = None
        logger.info(
            "Finished source %s in %s ms: fetched %s jobs, matched %s, added %s new jobs, "
            "deactivated %s, queued %s notifications",
            source_name,
            round((perf_counter() - started_at) * 1000),
            len(jobs),
            len(postings),
            len(new_ids),
            deactivated,
            notifications_enqueued,
        )
        return "success"
    except Exception as error:
        logger.exception("board.sync.failed source=%s error=%s", source_name, error)
        with session_factory.begin() as session:
            source = session.scalar(select(Source).where(Source.name == source_name))
            if source is not None:
                source.last_sync_status = "failed"
                source.last_sync_error = str(error)[:1000]
        return "failed"


@retry(
    retry=retry_if_exception_type(
        (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
    ),
    wait=wait_random_exponential(multiplier=0.25, max=4),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _fetch_with_retries(
    client: httpx.Client,
    platform: str,
    board_name: str,
    platform_config: dict[str, str] | None = None,
) -> list[BoardJob]:
    return fetch_board(client, cast(Platform, platform), board_name, platform_config)
