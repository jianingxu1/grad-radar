from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import event
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
    listed_at: datetime | None,
    title: str = "Software Engineer, New Grad",
) -> ParsedJobPosting:
    return ParsedJobPosting(
        source_name=SourceName.SIMPLIFY,
        company_name=company_name,
        title=title,
        apply_url=application_key,
        application_key=application_key,
        location=location,
        listed_at=listed_at,
    )


def test_jobs_api_filters_paginates_and_returns_listing_attributes(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory.begin() as session:
        bootstrap_sources(session)
        recent = persist_posting(
            session,
            _posting(
                "https://jobs.example.com/1", "Stripe", "Remote, USA", now - timedelta(hours=1)
            ),
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
        newest = persist_posting(
            session,
            _posting(
                "https://jobs.example.com/3",
                "Figma",
                "Boston, MA",
                now,
                title="Platform Engineer, New Grad",
            ),
            now - timedelta(hours=2),
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
        "listed_at": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "first_seen_at": now.isoformat().replace("+00:00", "Z"),
        "sources": [
            {"name": "simplify", "url": "https://github.com/SimplifyJobs/New-Grad-Positions"}
        ],
    }

    all_jobs = client.get("/v1/jobs")
    assert [job["id"] for job in all_jobs.json()["items"]] == [
        str(newest.id),
        str(recent.id),
        str(older.id),
    ]

    assert [job["id"] for job in client.get("/v1/jobs?company=stripe").json()["items"]] == [
        str(recent.id)
    ]
    assert [job["id"] for job in client.get("/v1/jobs?location=new%20york").json()["items"]] == [
        str(older.id)
    ]
    assert [job["id"] for job in client.get("/v1/jobs?remote=false").json()["items"]] == [
        str(newest.id),
        str(older.id),
    ]
    assert [job["id"] for job in client.get("/v1/jobs?remote=true").json()["items"]] == [
        str(recent.id)
    ]
    assert [job["id"] for job in client.get("/v1/jobs?q=platform").json()["items"]] == [
        str(newest.id)
    ]
    assert [job["id"] for job in client.get("/v1/jobs?posted_within_hours=1").json()["items"]] == [
        str(recent.id)
    ]
    assert [job["id"] for job in client.get("/v1/jobs?offset=1&limit=1").json()["items"]] == [
        str(recent.id)
    ]


def test_jobs_api_loads_provenance_in_one_batched_query(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory.begin() as session:
        bootstrap_sources(session)
        persist_posting(
            session,
            _posting("https://jobs.example.com/1", "Stripe", "Remote, USA", now),
            now,
        )
        persist_posting(
            session,
            ParsedJobPosting(
                source_name=SourceName.SPEEDYAPPLY,
                company_name="Stripe",
                title="Software Engineer, New Grad",
                apply_url="https://jobs.example.com/1",
                application_key="https://jobs.example.com/1",
                location="Remote, USA",
                listed_at=now,
            ),
            now,
        )
        persist_posting(
            session,
            _posting("https://jobs.example.com/2", "Figma", "Boston, MA", now),
            now,
        )

    statements: list[str] = []

    def count_selects(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    engine = session_factory.kw["bind"].engine
    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        response = TestClient(create_app(session_factory)).get("/v1/jobs")
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert response.status_code == 200
    assert len(statements) == 2
