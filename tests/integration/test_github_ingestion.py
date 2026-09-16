from datetime import UTC, datetime
from pathlib import Path

import respx
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPosting, JobPostingSource, Source
from app.services.github_ingestion import ingest_all, ingest_source
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
            first_summary = ingest_source(session_factory, client, definition)
            assert first_summary.status == "success"
            assert len(first_summary.new_job_ids) == 3
            previous_sync_at = datetime(2026, 1, 1, tzinfo=UTC)
            with session_factory.begin() as session:
                source = session.scalar(select(Source).where(Source.name == definition.name))
                assert source is not None
                source.last_successful_sync_at = previous_sync_at
            assert ingest_source(session_factory, client, definition).status == "unchanged"

    assert commit_route.call_count == 2
    assert raw_route.call_count == 1
    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.name == definition.name))
        assert source is not None
        assert source.last_processed_revision_sha == sha
        assert source.last_successful_sync_at is not None
        assert source.last_successful_sync_at > previous_sync_at
        assert len(session.scalars(select(JobPosting)).all()) == 3


def test_worker_updates_all_source_freshness_for_unchanged_revisions(
    session_factory: sessionmaker[Session],
) -> None:
    shas = {
        SourceName.SIMPLIFY: "e" * 40,
        SourceName.SPEEDYAPPLY: "f" * 40,
    }
    fixtures = {
        SourceName.SIMPLIFY: Path(__file__).parents[1] / "fixtures" / "simplify_new_grad.md",
        SourceName.SPEEDYAPPLY: (
            Path(__file__).parents[1] / "fixtures" / "speedyapply_new_grad.md"
        ),
    }

    with respx.mock:
        commit_routes = {}
        raw_routes = {}
        for definition in SOURCES:
            commit_routes[definition.name] = respx.get(
                f"https://api.github.com/repos/{definition.repository}/commits",
                params={"sha": definition.branch, "path": definition.file_path, "per_page": "1"},
            ).mock(return_value=_commit_response(shas[definition.name]))
            raw_routes[definition.name] = respx.get(
                "https://raw.githubusercontent.com/"
                f"{definition.repository}/{shas[definition.name]}/{definition.file_path}"
            ).mock(return_value=Response(200, text=fixtures[definition.name].read_text()))

        summaries = ingest_all(session_factory)
        assert [summary.status for summary in summaries] == ["success", "success"]

        previous_sync_at = datetime(2026, 1, 1, tzinfo=UTC)
        with session_factory.begin() as session:
            for definition in SOURCES:
                source = session.scalar(select(Source).where(Source.name == definition.name))
                assert source is not None
                source.last_successful_sync_at = previous_sync_at

        summaries = ingest_all(session_factory)
        assert [summary.status for summary in summaries] == ["unchanged", "unchanged"]

    assert all(route.call_count == 2 for route in commit_routes.values())
    assert all(route.call_count == 1 for route in raw_routes.values())
    with session_factory() as session:
        freshness = {
            source.name: source.last_successful_sync_at
            for source in session.scalars(select(Source)).all()
        }
    assert set(freshness) == {str(SourceName.SIMPLIFY), str(SourceName.SPEEDYAPPLY)}
    assert all(
        synced_at is not None and synced_at > previous_sync_at for synced_at in freshness.values()
    )


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
        assert source.last_successful_sync_at is None


def test_ingestion_does_not_mark_raw_fetch_failure_successful(
    session_factory: sessionmaker[Session],
) -> None:
    definition = next(source for source in SOURCES if source.name is SourceName.SIMPLIFY)
    sha = "d" * 40
    commit_url = f"https://api.github.com/repos/{definition.repository}/commits"
    raw_url = (
        f"https://raw.githubusercontent.com/{definition.repository}/{sha}/{definition.file_path}"
    )

    with respx.mock:
        respx.get(
            commit_url,
            params={"sha": definition.branch, "path": definition.file_path, "per_page": "1"},
        ).mock(return_value=_commit_response(sha))
        respx.get(raw_url).mock(return_value=Response(404))

        import httpx

        with httpx.Client() as client:
            summary = ingest_source(session_factory, client, definition)

    assert summary.status == "failed"
    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.name == definition.name))
        assert source is not None
        assert source.last_processed_revision_sha is None
        assert source.last_successful_sync_at is None


def test_ingestion_backfills_missing_source_positions_for_unchanged_revision(
    session_factory: sessionmaker[Session],
) -> None:
    definition = next(source for source in SOURCES if source.name is SourceName.SPEEDYAPPLY)
    fixture = Path(__file__).parents[1] / "fixtures" / "speedyapply_new_grad.md"
    sha = "c" * 40
    commit_url = f"https://api.github.com/repos/{definition.repository}/commits"
    raw_url = (
        f"https://raw.githubusercontent.com/{definition.repository}/{sha}/{definition.file_path}"
    )

    with respx.mock:
        respx.get(
            commit_url,
            params={"sha": definition.branch, "path": definition.file_path, "per_page": "1"},
        ).mock(return_value=_commit_response(sha))
        raw_route = respx.get(raw_url).mock(return_value=Response(200, text=fixture.read_text()))

        import httpx

        with httpx.Client() as client:
            assert ingest_source(session_factory, client, definition).status == "success"
            with session_factory.begin() as session:
                source = session.scalar(select(Source).where(Source.name == definition.name))
                assert source is not None
                for link in session.scalars(
                    select(JobPostingSource).where(JobPostingSource.source_id == source.id)
                ):
                    link.source_position = None
            assert ingest_source(session_factory, client, definition).status == "success"

    assert raw_route.call_count == 2
    with session_factory() as session:
        assert all(
            link.source_position is not None
            for link in session.scalars(select(JobPostingSource)).all()
        )
