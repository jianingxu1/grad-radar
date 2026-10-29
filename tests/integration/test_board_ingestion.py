from threading import Barrier, Lock
from typing import Any

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPosting, JobPostingSource, Source
from app.main import create_app
from app.services import board_ingestion
from app.sources.board_filter import DEFAULT_FILTER


def _sync(session_factory: sessionmaker[Session], client: httpx.Client) -> str:
    return board_ingestion.ingest_board(session_factory, client, "greenhouse:stripe")


@respx.mock
def test_smartrecruiters_fetches_details_only_for_possible_title_matches() -> None:
    base = "https://api.smartrecruiters.com/v1/companies/LinkedIn3/postings"
    listing = respx.get(base).mock(
        return_value=httpx.Response(
            200,
            json={
                "totalFound": 5,
                "content": [
                    {"id": "1", "name": "Software Engineer, New Grad"},
                    {"id": "3", "name": "Senior Software Engineer, New Grad"},
                    {"id": "2", "name": "Software Developer"},
                    {"id": "4", "name": "Accountant"},
                    {"id": "5"},
                ],
            },
        )
    )
    for posting_id, title, description in (
        ("1", "Software Engineer, New Grad", ""),
        ("2", "Software Developer", "Graduation expected between 2026 and 2027."),
        ("5", "Accountant", ""),
    ):
        respx.get(f"{base}/{posting_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": posting_id,
                    "name": title,
                    "location": {"city": "San Francisco", "region": "CA", "country": "us"},
                    "typeOfEmployment": {"label": "Full-time"},
                    "applyUrl": f"https://jobs.smartrecruiters.com/LinkedIn3/{posting_id}",
                    "jobAd": {"sections": {"jobDescription": {"text": description}}},
                },
            )
        )
    source = board_ingestion.BoardSource(
        "smartrecruiters:linkedin3", "smartrecruiters", "LinkedIn3", "LinkedIn", DEFAULT_FILTER
    )
    with httpx.Client() as client:
        result = board_ingestion._fetch_and_filter(client, source)

    assert result.error is None
    assert result.fetched_count == 3
    assert [posting.title for posting in result.postings or []] == [
        "Software Engineer, New Grad",
        "Software Developer",
    ]
    assert [posting.source_position for posting in result.postings or []] == [0, 2]
    assert listing.call_count == 1
    assert len(respx.calls) == 4


def _job(posting_id: str, title: str = "Software Engineer, New Grad") -> dict[str, Any]:
    return {
        "id": posting_id,
        "internal_job_id": 100,
        "title": title,
        "location": {"name": "San Francisco, CA"},
        "absolute_url": f"https://job-boards.greenhouse.io/stripe/jobs/{posting_id}",
    }


def _add_board(session: Session, name: str, board_name: str | None = None) -> None:
    session.add(
        Source(
            name=name,
            url=f"https://job-boards.greenhouse.io/{board_name or name}",
            platform="greenhouse",
            board_name=board_name or name,
            company_name=name,
            filter_config=DEFAULT_FILTER,
            priority=100,
        )
    )


@respx.mock
def test_board_first_sync_alerts_only_later_jobs_and_reconciles_closures(
    session_factory: sessionmaker[Session], monkeypatch: Any
) -> None:
    with session_factory.begin() as session:
        session.add(
            Source(
                name="greenhouse:stripe",
                url="https://job-boards.greenhouse.io/stripe",
                platform="greenhouse",
                board_name="stripe",
                company_name="Stripe",
                filter_config=DEFAULT_FILTER,
                priority=100,
            )
        )
    route = respx.get("https://boards-api.greenhouse.io/v1/boards/stripe/jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [_job("123")]})
    )
    alerts: list[list] = []
    monkeypatch.setattr(
        board_ingestion,
        "enqueue_new_jobs",
        lambda session, ids, now: alerts.append(ids),
    )
    with httpx.Client() as client:
        assert _sync(session_factory, client) == "success"
        assert alerts == []
        route.mock(return_value=httpx.Response(200, json={"jobs": [_job("123"), _job("124")]}))
        assert _sync(session_factory, client) == "success"
        assert len(alerts) == 1 and len(alerts[0]) == 1
        route.mock(return_value=httpx.Response(200, json={"jobs": []}))
        assert _sync(session_factory, client) == "success"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(JobPosting)) == 2
        assert all(not link.active for link in session.scalars(select(JobPostingSource)))
    assert TestClient(create_app(session_factory)).get("/v1/jobs").json()["total"] == 0


@respx.mock
def test_failed_sync_keeps_existing_board_links(session_factory: sessionmaker[Session]) -> None:
    with session_factory.begin() as session:
        session.add(
            Source(
                name="greenhouse:stripe",
                url="https://job-boards.greenhouse.io/stripe",
                platform="greenhouse",
                board_name="stripe",
                company_name="Stripe",
                filter_config=DEFAULT_FILTER,
            )
        )
    route = respx.get("https://boards-api.greenhouse.io/v1/boards/stripe/jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [_job("123")]})
    )
    with httpx.Client() as client:
        assert _sync(session_factory, client) == "success"
        route.mock(return_value=httpx.Response(200, json={"bad": []}))
        assert _sync(session_factory, client) == "failed"
    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.name == "greenhouse:stripe"))
        assert source is not None and source.last_sync_status == "failed"
        assert session.scalar(select(JobPostingSource.active)) is True


@respx.mock
def test_filter_edit_hides_previously_accepted_job(session_factory: sessionmaker[Session]) -> None:
    with session_factory.begin() as session:
        session.add(
            Source(
                name="greenhouse:stripe",
                url="https://job-boards.greenhouse.io/stripe",
                platform="greenhouse",
                board_name="stripe",
                company_name="Stripe",
                filter_config=DEFAULT_FILTER,
            )
        )
    respx.get("https://boards-api.greenhouse.io/v1/boards/stripe/jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [_job("123")]})
    )
    with httpx.Client() as client:
        assert _sync(session_factory, client) == "success"
        with session_factory.begin() as session:
            source = session.scalar(select(Source).where(Source.name == "greenhouse:stripe"))
            assert source is not None
            source.filter_config = {**DEFAULT_FILTER, "level_terms": ["graduate engineer"]}
        assert _sync(session_factory, client) == "success"
    with session_factory() as session:
        assert session.scalar(select(JobPostingSource.active)) is False


def test_board_workers_receive_settings_and_filter_without_database_access(
    monkeypatch: Any,
) -> None:
    source = board_ingestion.BoardSource(
        name="greenhouse:example",
        platform="greenhouse",
        board_name="example",
        company_name="Example",
        filter_config=DEFAULT_FILTER,
        platform_config=None,
    )
    fetched: list[tuple[str, str]] = []
    normalized: list[tuple[str, str, str]] = []

    def fetch(
        client: httpx.Client,
        platform: str,
        board_name: str,
        platform_config: dict[str, str] | None = None,
    ) -> list:
        fetched.append((platform, board_name))
        return []

    def normalize(jobs: list, source_name: str, config: dict, company_name: str) -> list:
        normalized.append((source_name, company_name, config["role_terms"][0]))
        return []

    monkeypatch.setattr(board_ingestion, "_fetch_with_retries", fetch)
    monkeypatch.setattr(board_ingestion, "normalize_board_jobs", normalize)
    with httpx.Client() as client:
        result = board_ingestion._fetch_and_filter(client, source)

    assert result.error is None
    assert result.postings == []
    assert fetched == [("greenhouse", "example")]
    assert normalized == [("greenhouse:example", "Example", DEFAULT_FILTER["role_terms"][0])]


def test_ingest_all_boards_runs_at_most_eight_fetch_workers(
    session_factory: sessionmaker[Session], monkeypatch: Any
) -> None:
    with session_factory.begin() as session:
        for index in range(10):
            _add_board(session, f"greenhouse:company-{index}", f"company-{index}")

    barrier = Barrier(board_ingestion.MAX_BOARD_WORKERS)
    lock = Lock()
    active = 0
    maximum = 0
    calls = 0

    def fetch(
        client: httpx.Client,
        platform: str,
        board_name: str,
        platform_config: dict[str, str] | None = None,
    ) -> list:
        nonlocal active, maximum, calls
        with lock:
            calls += 1
            call_number = calls
            active += 1
            maximum = max(maximum, active)
        if call_number <= board_ingestion.MAX_BOARD_WORKERS:
            barrier.wait(timeout=10)
        with lock:
            active -= 1
        return []

    monkeypatch.setattr(board_ingestion, "_fetch_with_retries", fetch)
    results = board_ingestion.ingest_all_boards(session_factory)

    assert len(results) == 10
    assert all(status == "success" for _, status in results)
    assert maximum == board_ingestion.MAX_BOARD_WORKERS == 8


def test_ingest_all_boards_records_failure_and_continues(
    session_factory: sessionmaker[Session], monkeypatch: Any, caplog: Any
) -> None:
    with session_factory.begin() as session:
        _add_board(session, "greenhouse:bad", "bad")
        _add_board(session, "greenhouse:good", "good")

    def fetch(
        client: httpx.Client,
        platform: str,
        board_name: str,
        platform_config: dict[str, str] | None = None,
    ) -> list:
        if board_name == "bad":
            raise ValueError("bad board response")
        return []

    monkeypatch.setattr(board_ingestion, "_fetch_with_retries", fetch)
    results = dict(board_ingestion.ingest_all_boards(session_factory))

    assert results == {"greenhouse:bad": "failed", "greenhouse:good": "success"}
    failure_log = next(
        record
        for record in caplog.records
        if record.message.startswith("board.sync.failed source=greenhouse:bad")
    )
    assert failure_log.exc_info is not None
    with session_factory() as session:
        bad = session.scalar(select(Source).where(Source.name == "greenhouse:bad"))
        good = session.scalar(select(Source).where(Source.name == "greenhouse:good"))
        assert bad is not None and bad.last_sync_status == "failed"
        assert bad.last_sync_error == "bad board response"
        assert good is not None and good.last_sync_status == "success"
