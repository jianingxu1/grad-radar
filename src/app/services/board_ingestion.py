"""Ingest configured public company boards independently."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast

import httpx
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from app.database.models import JobPostingSource, Source
from app.models.parsed_job_posting import ParsedJobPosting
from app.repositories.job_postings import persist_postings_with_new_ids
from app.services.notifications import enqueue_new_jobs
from app.sources.ats import BoardJob, Platform, fetch_board
from app.sources.board_filter import DEFAULT_FILTER, normalize_board_jobs, validate_filter

logger = logging.getLogger(__name__)
MAX_BOARD_WORKERS = 8


@dataclass(frozen=True)
class BoardSource:
    name: str
    platform: str
    board_name: str | None
    company_name: str | None
    filter_config: dict[str, Any] | None
    platform_config: dict[str, str] | None = None


@dataclass
class BoardFetchResult:
    source: BoardSource
    started_at: float
    fetched_count: int = 0
    postings: list[ParsedJobPosting] | None = None
    error: Exception | None = None


def ingest_all_boards(session_factory: sessionmaker[Session]) -> list[tuple[str, str]]:
    with session_factory() as session:
        sources = [
            BoardSource(
                name=source.name,
                platform=source.platform,
                board_name=source.board_name,
                company_name=source.company_name,
                filter_config=source.filter_config,
                platform_config=source.platform_config,
            )
            for source in session.scalars(
                select(Source).where(Source.enabled, Source.platform != "github")
            ).all()
        ]

    logger.info("Starting company board ingestion for %s sources", len(sources))
    results_by_name: dict[str, str] = {}
    with (
        httpx.Client(timeout=20) as client,
        ThreadPoolExecutor(max_workers=MAX_BOARD_WORKERS) as executor,
    ):
        futures = {executor.submit(_fetch_and_filter, client, source): source for source in sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
            except Exception as error:  # Defensive: workers normally return errors in results.
                result = BoardFetchResult(source, perf_counter(), error=error)
            results_by_name[source.name] = _persist_result(session_factory, result)

    return [(source.name, results_by_name[source.name]) for source in sources]


def ingest_board(
    session_factory: sessionmaker[Session], client: httpx.Client, source_name: str
) -> str:
    """Synchronously ingest one board; retained for direct callers and focused tests."""
    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.name == source_name))
        if source is None or not source.enabled or source.platform == "github":
            raise ValueError("unknown or disabled board source")
        board_source = BoardSource(
            name=source.name,
            platform=source.platform,
            board_name=source.board_name,
            company_name=source.company_name,
            filter_config=source.filter_config,
            platform_config=source.platform_config,
        )
    return _persist_result(session_factory, _fetch_and_filter(client, board_source))


def _fetch_and_filter(client: httpx.Client, source: BoardSource) -> BoardFetchResult:
    started_at = perf_counter()
    try:
        if not source.board_name or not source.company_name:
            raise ValueError("board source is missing its name or company")
        logger.info("Fetching jobs from %s board %s", source.platform, source.board_name)
        jobs = _fetch_with_retries(
            client, source.platform, source.board_name, source.platform_config
        )
        logger.info("Filtering %s fetched jobs from source %s", len(jobs), source.name)
        postings = normalize_board_jobs(
            jobs,
            source.name,
            validate_filter(source.filter_config or DEFAULT_FILTER),
            source.company_name,
        )
        return BoardFetchResult(source, started_at, len(jobs), postings)
    except Exception as error:
        return BoardFetchResult(source, started_at, error=error)


def _persist_result(session_factory: sessionmaker[Session], result: BoardFetchResult) -> str:
    source_name = result.source.name
    try:
        if result.error is not None:
            raise result.error
        if result.postings is None:
            raise RuntimeError("board fetch returned no postings")

        checked_at = datetime.now(UTC)
        with session_factory.begin() as session:
            source = session.scalar(select(Source).where(Source.name == source_name))
            if source is None or not source.enabled:
                raise ValueError("board source was disabled during sync")
            stored_jobs, new_ids = persist_postings_with_new_ids(
                session, result.postings, checked_at
            )
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
            round((perf_counter() - result.started_at) * 1000),
            result.fetched_count,
            len(result.postings),
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
