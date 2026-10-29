"""Ingest configured public company boards independently."""

import logging
from datetime import UTC, datetime
from typing import cast

import httpx
from sqlalchemy import select, update
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
    with httpx.Client(timeout=20) as client:
        for name in names:
            results.append((name, ingest_board(session_factory, client, name)))
    return results


def ingest_board(
    session_factory: sessionmaker[Session], client: httpx.Client, source_name: str
) -> str:
    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.name == source_name))
        if source is None or not source.enabled or source.platform == "github":
            raise ValueError("unknown or disabled board source")
        platform = source.platform
        board_name = source.board_name
        company_name = source.company_name
        config = source.filter_config or DEFAULT_FILTER
    if not board_name or not company_name:
        raise ValueError("board source is missing its name or company")
    try:
        jobs = _fetch_with_retries(client, platform, board_name)
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
            session.execute(deactivate.values(active=False))
            if source.initial_sync_completed:
                enqueue_new_jobs(session, new_ids, checked_at)
            source.initial_sync_completed = True
            source.last_successful_sync_at = checked_at
            source.last_sync_status = "success"
            source.last_sync_error = None
        logger.info(
            "board.sync.success source=%s fetched=%s matched=%s",
            source_name,
            len(jobs),
            len(postings),
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
def _fetch_with_retries(client: httpx.Client, platform: str, board_name: str) -> list[BoardJob]:
    return fetch_board(client, cast(Platform, platform), board_name)
