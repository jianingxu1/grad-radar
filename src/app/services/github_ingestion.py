import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from app.database.models import JobPostingSource, Source
from app.repositories.job_postings import persist_postings_with_new_ids
from app.services.notifications import enqueue_new_jobs
from app.sources.bootstrap import bootstrap_sources
from app.sources.definitions import SOURCES, SourceDefinition
from app.sources.parsing import ParseResult, get_parser

logger = logging.getLogger(__name__)


@dataclass
class IngestionSummary:
    source: str
    status: str
    sha: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    parsed: int | None = None
    eligible: int | None = None
    ineligible: int | None = None
    unknown: int | None = None
    malformed: int | None = None
    new_job_ids: list[UUID] = field(default_factory=list)


def ingest_all(
    session_factory: sessionmaker[Session], github_token: str | None = None
) -> list[IngestionSummary]:
    started_at = perf_counter()
    logger.info("ingestion.batch.started source_count=%s", len(SOURCES))
    headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}
    cycle_at = datetime.now(UTC)
    with httpx.Client(headers=headers, timeout=20) as client:
        summaries = [ingest_source(session_factory, client, source) for source in SOURCES]
    new_ids = [job_id for summary in summaries for job_id in summary.new_job_ids]
    notifications_enqueued = 0
    if new_ids:
        with session_factory.begin() as session:
            notifications_enqueued = enqueue_new_jobs(session, new_ids, cycle_at)
    logger.info(
        "ingestion.batch.completed duration_ms=%s successful=%s unchanged=%s failed=%s "
        "new_jobs=%s notifications_enqueued=%s",
        _duration_ms(started_at),
        sum(summary.status == "success" for summary in summaries),
        sum(summary.status == "unchanged" for summary in summaries),
        sum(summary.status == "failed" for summary in summaries),
        len(new_ids),
        notifications_enqueued,
    )
    return summaries


def ingest_source(
    session_factory: sessionmaker[Session], client: httpx.Client, definition: SourceDefinition
) -> IngestionSummary:
    started_at = perf_counter()
    sha: str | None = None
    logger.info("ingestion.source.started source=%s", definition.name)
    try:
        commit = _get(
            client,
            f"https://api.github.com/repos/{definition.repository}/commits",
            params={"sha": definition.branch, "path": definition.file_path, "per_page": 1},
        )
        checked_at = datetime.now(UTC)
        payload = commit.json()[0]
        sha = payload["sha"]
        revision_at = datetime.fromisoformat(
            payload["commit"]["committer"]["date"].replace("Z", "+00:00")
        ).astimezone(UTC)
        with session_factory.begin() as session:
            bootstrap_sources(session)
            source = session.query(Source).filter_by(name=definition.name).one()
            needs_position_backfill = session.scalar(
                select(JobPostingSource.job_posting_id)
                .where(
                    JobPostingSource.source_id == source.id,
                    JobPostingSource.source_position.is_(None),
                )
                .limit(1)
            )
            unchanged = (
                source.last_processed_revision_sha == sha and needs_position_backfill is None
            )
        if unchanged:
            _mark_source_successfully_synced(session_factory, definition, checked_at)
            duration_ms = _duration_ms(started_at)
            logger.info(
                "ingestion.source.unchanged source=%s sha=%s duration_ms=%s",
                definition.name,
                sha,
                duration_ms,
            )
            return IngestionSummary(definition.name, "unchanged", sha, duration_ms=duration_ms)
        raw = _get(
            client,
            f"https://raw.githubusercontent.com/{definition.repository}/{sha}/{definition.file_path}",
        )
        checked_at = datetime.now(UTC)
        parsed: ParseResult = get_parser(definition.parser).parse(raw.text, revision_at)
        logger.info(
            "ingestion.source.parsed source=%s sha=%s parsed=%s eligible=%s "
            "ineligible=%s unknown=%s malformed=%s",
            definition.name,
            sha,
            parsed.parsed,
            len(parsed.postings),
            parsed.ineligible,
            parsed.unknown,
            parsed.malformed,
        )
        with session_factory.begin() as session:
            source = session.query(Source).filter_by(name=definition.name).one()
            _, new_job_ids = persist_postings_with_new_ids(session, parsed.postings, checked_at)
            source.last_processed_revision_sha = sha
        _mark_source_successfully_synced(session_factory, definition, checked_at)
        duration_ms = _duration_ms(started_at)
        summary = IngestionSummary(
            definition.name,
            "success",
            sha,
            duration_ms=duration_ms,
            parsed=parsed.parsed,
            eligible=len(parsed.postings),
            ineligible=parsed.ineligible,
            unknown=parsed.unknown,
            malformed=parsed.malformed,
            new_job_ids=new_job_ids,
        )
        logger.info(
            "ingestion.source.completed source=%s sha=%s duration_ms=%s parsed=%s "
            "eligible=%s ineligible=%s unknown=%s malformed=%s new_jobs=%s",
            summary.source,
            summary.sha,
            summary.duration_ms,
            summary.parsed,
            summary.eligible,
            summary.ineligible,
            summary.unknown,
            summary.malformed,
            len(summary.new_job_ids),
        )
        return summary
    except Exception as error:
        duration_ms = _duration_ms(started_at)
        logger.exception(
            "ingestion.source.failed source=%s sha=%s duration_ms=%s error=%s",
            definition.name,
            sha,
            duration_ms,
            error,
        )
        return IngestionSummary(definition.name, "failed", sha, str(error), duration_ms=duration_ms)


@retry(
    retry=retry_if_exception_type(
        (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
    ),
    wait=wait_random_exponential(multiplier=0.25, max=4),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _get(client: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    response = client.get(url, **kwargs)
    if response.status_code == 429 or response.status_code >= 500:
        raise httpx.HTTPStatusError(
            "retryable GitHub response", request=response.request, response=response
        )
    response.raise_for_status()
    return response


def _mark_source_successfully_synced(
    session_factory: sessionmaker[Session], definition: SourceDefinition, checked_at: datetime
) -> None:
    with session_factory.begin() as session:
        source = session.query(Source).filter_by(name=definition.name).one()
        source.last_successful_sync_at = checked_at


def _duration_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)
