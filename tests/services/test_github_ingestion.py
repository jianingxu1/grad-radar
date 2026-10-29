from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy.orm import Session, sessionmaker

import app.services.github_ingestion as ingestion
from app.sources.definitions import SOURCES, SourceName


def test_enqueue_failure_occurs_before_source_transaction_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = next(source for source in SOURCES if source.name is SourceName.SPEEDYAPPLY)
    fixture = Path(__file__).parents[1] / "fixtures" / "speedyapply_new_grad.md"
    sha = "7" * 40
    source = SimpleNamespace(
        id=uuid4(), last_processed_revision_sha=None, last_successful_sync_at=None
    )
    session = Mock()
    session.query.return_value.filter_by.return_value.one.return_value = source
    session.scalar.return_value = None
    events: list[str] = []

    @contextmanager
    def begin() -> Iterator[Mock]:
        events.append("begin")
        try:
            yield session
        except Exception:
            events.append("rollback")
            raise
        else:
            events.append("commit")

    factory = cast(sessionmaker[Session], SimpleNamespace(begin=begin))
    new_id: UUID = uuid4()
    monkeypatch.setattr(ingestion, "bootstrap_sources", lambda _session: None)
    monkeypatch.setattr(ingestion, "persist_postings_with_new_ids", lambda *_args: ([], [new_id]))

    def fail_enqueue(_session: Any, _job_ids: list[UUID], _at: datetime) -> int:
        events.append("enqueue")
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(ingestion, "enqueue_new_jobs", fail_enqueue)
    with respx.mock:
        respx.get(
            f"https://api.github.com/repos/{definition.repository}/commits",
            params={"sha": definition.branch, "path": definition.file_path, "per_page": "1"},
        ).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "sha": sha,
                        "commit": {"committer": {"date": "2026-01-03T00:00:00Z"}},
                    }
                ],
            )
        )
        respx.get(
            f"https://raw.githubusercontent.com/{definition.repository}/{sha}/{definition.file_path}"
        ).mock(return_value=Response(200, text=fixture.read_text()))

        with httpx.Client() as client:
            summary = ingestion.ingest_source(
                factory, client, definition, cycle_at=datetime(2026, 1, 3, tzinfo=UTC)
            )

    assert summary.status == "failed"
    assert events == ["begin", "commit", "begin", "enqueue", "rollback", "begin", "commit"]
    assert source.last_processed_revision_sha is None
