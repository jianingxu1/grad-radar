import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session, sessionmaker
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from gradradar.database.models import JobPostingSource, Source
from gradradar.repositories.job_postings import persist_posting
from gradradar.sources.bootstrap import bootstrap_sources
from gradradar.sources.definitions import SOURCES, SourceDefinition
from gradradar.sources.parsers import ParseResult, parse_simplify, parse_speedyapply

logger = logging.getLogger(__name__)


@dataclass
class IngestionSummary:
    source: str
    status: str
    sha: str | None = None
    error: str | None = None


def ingest_all(
    session_factory: sessionmaker[Session], github_token: str | None = None
) -> list[IngestionSummary]:
    headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}
    with httpx.Client(headers=headers, timeout=20) as client:
        return [ingest_source(session_factory, client, source) for source in SOURCES]


def ingest_source(
    session_factory: sessionmaker[Session], client: httpx.Client, definition: SourceDefinition
) -> IngestionSummary:
    try:
        commit = _get(
            client,
            f"https://api.github.com/repos/{definition.repository}/commits",
            params={"sha": definition.branch, "path": definition.file_path, "per_page": 1},
        )
        commit.raise_for_status()
        payload = commit.json()[0]
        sha = payload["sha"]
        revision_at = datetime.fromisoformat(
            payload["commit"]["committer"]["date"].replace("Z", "+00:00")
        ).astimezone(UTC)
        with session_factory.begin() as session:
            bootstrap_sources(session)
            source = session.query(Source).filter_by(name=definition.name).one()
            if source.last_processed_revision_sha == sha:
                return IngestionSummary(definition.name, "unchanged", sha)
        raw = _get(
            client,
            f"https://raw.githubusercontent.com/{definition.repository}/{sha}/{definition.file_path}",
        )
        raw.raise_for_status()
        parsed: ParseResult = (
            parse_simplify if definition.parser == "simplify" else parse_speedyapply
        )(raw.text, revision_at)
        with session_factory.begin() as session:
            source = session.query(Source).filter_by(name=definition.name).one()
            prior_count = session.query(JobPostingSource).filter_by(source_id=source.id).count()
            if prior_count >= 20 and len(parsed.postings) <= prior_count * 0.2:
                raise ValueError(
                    "suspicious eligible posting drop: "
                    f"prior={prior_count}, new={len(parsed.postings)}"
                )
            for posting in parsed.postings:
                persist_posting(session, posting, datetime.now(UTC))
            source.last_processed_revision_sha, source.last_successful_sync_at = (
                sha,
                datetime.now(UTC),
            )
        return IngestionSummary(definition.name, "success", sha)
    except Exception as error:
        logger.exception("source ingestion failed", extra={"source": definition.name})
        return IngestionSummary(definition.name, "failed", error=str(error))


@retry(
    retry=retry_if_exception_type(
        (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
    ),
    wait=wait_random_exponential(multiplier=0.25, max=4),
    stop=stop_after_attempt(3),
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
