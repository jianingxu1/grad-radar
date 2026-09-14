import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session, sessionmaker

from gradradar.bootstrap import bootstrap_sources
from gradradar.parsers import ParseResult, parse_simplify, parse_speedyapply
from gradradar.persistence import persist_posting
from gradradar.source_config import SOURCES, SourceDefinition

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
        commit = client.get(
            f"https://api.github.com/repos/{definition.repository}/commits",
            params={"sha": definition.branch, "path": definition.file_path, "per_page": 1},
        )
        commit.raise_for_status()
        payload = commit.json()[0]
        sha = payload["sha"]
        revision_at = datetime.fromisoformat(
            payload["commit"]["committer"]["date"].replace("Z", "+00:00")
        ).astimezone(UTC)
        with session_factory() as session:
            bootstrap_sources(session)
            from gradradar.models import Source

            source = session.query(Source).filter_by(name=definition.name).one()
            if source.last_processed_revision_sha == sha:
                session.commit()
                return IngestionSummary(definition.name, "unchanged", sha)
        raw = client.get(
            f"https://raw.githubusercontent.com/{definition.repository}/{sha}/{definition.file_path}"
        )
        raw.raise_for_status()
        parsed: ParseResult = (
            parse_simplify if definition.parser == "simplify" else parse_speedyapply
        )(raw.text, revision_at)
        with session_factory.begin() as session:
            source = session.query(Source).filter_by(name=definition.name).one()
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
