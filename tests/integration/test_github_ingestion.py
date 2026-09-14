from pathlib import Path

import respx
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPosting, Source
from app.services.github_ingestion import ingest_source
from app.sources.definitions import SOURCES, SourceName


def _commit_response(sha: str) -> Response:
    return Response(
        200,
        json=[
            {
                "sha": sha,
                "commit": {"committer": {"date": "2026-01-03T00:00:00Z"}},
            }
        ],
    )


def test_ingestion_persists_changed_revision_and_skips_unchanged_revision(
    session_factory: sessionmaker[Session],
) -> None:
    definition = next(source for source in SOURCES if source.name is SourceName.SPEEDYAPPLY)
    fixture = Path(__file__).parents[1] / "fixtures" / "speedyapply_new_grad.md"
    sha = "a" * 40
    commit_url = f"https://api.github.com/repos/{definition.repository}/commits"
    raw_url = (
        f"https://raw.githubusercontent.com/{definition.repository}/{sha}/{definition.file_path}"
    )

    with respx.mock:
        commit_route = respx.get(
            commit_url,
            params={"sha": definition.branch, "path": definition.file_path, "per_page": "1"},
        ).mock(return_value=_commit_response(sha))
        raw_route = respx.get(raw_url).mock(return_value=Response(200, text=fixture.read_text()))

        import httpx

        with httpx.Client() as client:
            assert ingest_source(session_factory, client, definition).status == "success"
            assert ingest_source(session_factory, client, definition).status == "unchanged"

    assert commit_route.call_count == 2
    assert raw_route.call_count == 1
    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.name == definition.name))
        assert source is not None
        assert source.last_processed_revision_sha == sha
        assert len(session.scalars(select(JobPosting)).all()) == 3


def test_ingestion_does_not_advance_source_revision_when_parsing_fails(
    session_factory: sessionmaker[Session],
) -> None:
    definition = next(source for source in SOURCES if source.name is SourceName.SIMPLIFY)
    sha = "b" * 40
    commit_url = f"https://api.github.com/repos/{definition.repository}/commits"
    raw_url = (
        f"https://raw.githubusercontent.com/{definition.repository}/{sha}/{definition.file_path}"
    )

    with respx.mock:
        respx.get(
            commit_url,
            params={"sha": definition.branch, "path": definition.file_path, "per_page": "1"},
        ).mock(return_value=_commit_response(sha))
        respx.get(raw_url).mock(return_value=Response(200, text="# wrong source"))

        import httpx

        with httpx.Client() as client:
            summary = ingest_source(session_factory, client, definition)

    assert summary.status == "failed"
    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.name == definition.name))
        assert source is not None
        assert source.last_processed_revision_sha is None
