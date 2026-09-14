from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.main import create_app
from app.models.parsed_job_posting import ParsedJobPosting
from app.repositories.job_postings import persist_posting
from app.sources.bootstrap import bootstrap_sources
from app.sources.definitions import SourceName


def _posting(
    application_key: str,
    company_name: str,
    location: str,
    first_seen_at: datetime,
) -> ParsedJobPosting:
    return ParsedJobPosting(
        source_name=SourceName.SIMPLIFY,
        company_name=company_name,
        title="Software Engineer, New Grad",
        apply_url=application_key,
        application_key=application_key,
        location=location,
        listed_at=None,
    )


def test_jobs_api_filters_paginates_and_returns_listing_attributes(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory.begin() as session:
        bootstrap_sources(session)
        recent = persist_posting(
            session,
            _posting("https://jobs.example.com/1", "Stripe", "Remote, USA", now),
            now,
        )
        older = persist_posting(
            session,
            _posting(
                "https://jobs.example.com/2",
                "Other",
                "New York, NY",
                now - timedelta(days=2),
            ),
            now - timedelta(days=2),
        )

    client = TestClient(create_app(session_factory))
    response = client.get("/v1/jobs", params={"q": "stripe", "remote": "true", "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 1
    assert [job["id"] for job in body["items"]] == [str(recent.id)]
    assert body["items"][0] == {
        "id": str(recent.id),
        "company_name": "Stripe",
        "title": "Software Engineer, New Grad",
        "apply_url": "https://jobs.example.com/1",
        "location": "Remote, USA",
        "listed_at": None,
        "first_seen_at": now.isoformat().replace("+00:00", "Z"),
        "sources": [
            {"name": "simplify", "url": "https://github.com/SimplifyJobs/New-Grad-Positions"}
        ],
    }

    all_jobs = client.get("/v1/jobs")
    assert [job["id"] for job in all_jobs.json()["items"]] == [str(recent.id), str(older.id)]
