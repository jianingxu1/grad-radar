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


def _job(posting_id: str, title: str = "Software Engineer, New Grad") -> dict[str, Any]:
    return {
        "id": posting_id,
        "internal_job_id": 100,
        "title": title,
        "location": {"name": "San Francisco, CA"},
        "absolute_url": f"https://job-boards.greenhouse.io/stripe/jobs/{posting_id}",
    }


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
