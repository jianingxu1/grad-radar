from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPostingSource, Source
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


def _mark_source_current(session: Session, source_name: SourceName, synced_at: datetime) -> None:
    source = session.scalar(select(Source).where(Source.name == source_name))
    assert source is not None
    source.last_successful_sync_at = synced_at
    for link in session.scalars(
        select(JobPostingSource).where(JobPostingSource.source_id == source.id)
    ):
        link.last_seen_at = synced_at


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
        _mark_source_current(session, SourceName.SIMPLIFY, now)

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


def test_jobs_api_excludes_jobs_absent_from_all_sources(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory.begin() as session:
        bootstrap_sources(session)
        current = persist_posting(
            session,
            _posting("https://jobs.example.com/current", "Current", "Boston, MA", now),
            now,
        )
        persist_posting(
            session,
            _posting("https://jobs.example.com/absent", "Absent", "Boston, MA", now),
            now - timedelta(days=1),
        )
        source = session.scalar(select(Source).where(Source.name == SourceName.SIMPLIFY))
        assert source is not None
        source.last_successful_sync_at = now

    response = TestClient(create_app(session_factory)).get("/v1/jobs")

    assert response.status_code == 200
    assert [job["id"] for job in response.json()["items"]] == [str(current.id)]


def test_health_endpoint(session_factory: sessionmaker[Session]) -> None:
    response = TestClient(create_app(session_factory)).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
        _mark_source_current(session, SourceName.SIMPLIFY, now)
        _mark_source_current(session, SourceName.SPEEDYAPPLY, now)
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
