from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPosting, JobPostingSource, Source
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
    source_position: int = 0,
) -> ParsedJobPosting:
    return ParsedJobPosting(
        source_name=SourceName.SIMPLIFY,
        company_name=company_name,
        title=title,
        apply_url=application_key,
        application_key=application_key,
        location=location,
        listed_at=listed_at,
        source_position=source_position,
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
    assert body["total"] == 1
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
    assert body["source_freshness"] == [
        {
            "name": "simplify",
            "url": "https://github.com/SimplifyJobs/New-Grad-Positions",
            "last_successful_sync_at": now.isoformat().replace("+00:00", "Z"),
        },
        {
            "name": "speedyapply",
            "url": "https://github.com/speedyapply/2027-SWE-College-Jobs",
            "last_successful_sync_at": None,
        },
    ]

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
    assert [job["id"] for job in client.get("/v1/jobs?listed_within_hours=24").json()["items"]] == [
        str(newest.id),
        str(recent.id),
    ]
    assert [job["id"] for job in client.get("/v1/jobs?offset=1&limit=1").json()["items"]] == [
        str(recent.id)
    ]
    assert [
        job["id"]
        for job in client.get("/v1/jobs?sort_by=company_name&sort_direction=asc").json()["items"]
    ] == [str(newest.id), str(older.id), str(recent.id)]
    assert [
        job["id"]
        for job in client.get("/v1/jobs?sort_by=listed_at&sort_direction=asc").json()["items"]
    ] == [str(older.id), str(recent.id), str(newest.id)]


def test_jobs_api_filters_discovered_jobs_by_source(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory.begin() as session:
        bootstrap_sources(session)
        simplify = persist_posting(
            session,
            _posting("https://jobs.example.com/simplify", "Simplify", "Boston, MA", now),
            now,
        )
        speedyapply = persist_posting(
            session,
            ParsedJobPosting(
                source_name=SourceName.SPEEDYAPPLY,
                company_name="SpeedyApply",
                title="Software Engineer, New Grad",
                apply_url="https://jobs.example.com/speedyapply",
                application_key="https://jobs.example.com/speedyapply",
                location="New York, NY",
                listed_at=now - timedelta(minutes=1),
                source_position=0,
            ),
            now,
        )
        _mark_source_current(session, SourceName.SIMPLIFY, now)
        _mark_source_current(session, SourceName.SPEEDYAPPLY, now)

    client = TestClient(create_app(session_factory))

    assert [job["id"] for job in client.get("/v1/jobs?sources=simplify").json()["items"]] == [
        str(simplify.id)
    ]
    assert [
        job["id"]
        for job in client.get("/v1/jobs?sources=simplify&sources=speedyapply").json()["items"]
    ] == [str(simplify.id), str(speedyapply.id)]


def test_jobs_api_listing_age_filter_uses_hours(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    yesterday_start = datetime.combine(now.date() - timedelta(days=1), time.min, UTC)
    with session_factory.begin() as session:
        bootstrap_sources(session)
        today = persist_posting(
            session,
            _posting("https://jobs.example.com/today", "Today", "Boston, MA", now),
            now,
        )
        yesterday = persist_posting(
            session,
            _posting(
                "https://jobs.example.com/yesterday", "Yesterday", "Boston, MA", yesterday_start
            ),
            now,
        )
        _mark_source_current(session, SourceName.SIMPLIFY, now)

    response = TestClient(create_app(session_factory)).get("/v1/jobs?listed_within_hours=48")

    assert response.status_code == 200
    assert [job["id"] for job in response.json()["items"]] == [str(today.id), str(yesterday.id)]


def test_jobs_api_includes_jobs_absent_from_latest_tracker_snapshot(
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
        absent = persist_posting(
            session,
            _posting(
                "https://jobs.example.com/absent",
                "Absent",
                "Boston, MA",
                now - timedelta(minutes=1),
            ),
            now - timedelta(days=1),
        )
        source = session.scalar(select(Source).where(Source.name == SourceName.SIMPLIFY))
        assert source is not None
        source.last_successful_sync_at = now

    response = TestClient(create_app(session_factory)).get("/v1/jobs")

    assert response.status_code == 200
    assert [job["id"] for job in response.json()["items"]] == [str(current.id), str(absent.id)]


def test_jobs_api_keeps_source_row_order_for_matching_listing_dates(
    session_factory: sessionmaker[Session],
) -> None:
    listed_at = datetime(2026, 1, 1, tzinfo=UTC)
    first_seen_at = datetime(2026, 1, 2, tzinfo=UTC)
    first_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    second_id = UUID("00000000-0000-0000-0000-000000000000")
    with session_factory.begin() as session:
        bootstrap_sources(session)
        simplify = session.scalar(select(Source).where(Source.name == SourceName.SIMPLIFY))
        assert simplify is not None
        simplify.last_successful_sync_at = first_seen_at
        session.add_all(
            [
                JobPosting(
                    id=first_id,
                    application_key="first",
                    company_name="First source row",
                    title="Software Engineer, New Grad",
                    apply_url="https://jobs.example.com/first",
                    location="Boston, MA",
                    listed_at=listed_at,
                    first_seen_at=first_seen_at,
                ),
                JobPosting(
                    id=second_id,
                    application_key="second",
                    company_name="Second source row",
                    title="Software Engineer, New Grad",
                    apply_url="https://jobs.example.com/second",
                    location="Boston, MA",
                    listed_at=listed_at,
                    first_seen_at=first_seen_at,
                ),
                JobPostingSource(
                    job_posting_id=first_id,
                    source_id=simplify.id,
                    last_seen_at=first_seen_at,
                    source_position=0,
                ),
                JobPostingSource(
                    job_posting_id=second_id,
                    source_id=simplify.id,
                    last_seen_at=first_seen_at,
                    source_position=1,
                ),
            ]
        )

    response = TestClient(create_app(session_factory)).get("/v1/jobs")

    assert response.status_code == 200
    assert [job["id"] for job in response.json()["items"]] == [str(first_id), str(second_id)]


def test_health_endpoint(session_factory: sessionmaker[Session]) -> None:
    response = TestClient(create_app(session_factory)).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint_introduces_the_api() -> None:
    response = TestClient(create_app()).get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "GradRadar API",
        "docs_url": "/docs",
        "health_url": "/health",
        "jobs_url": "/v1/jobs",
    }


def test_api_allows_configured_frontend_origin(session_factory: sessionmaker[Session]) -> None:
    response = TestClient(create_app(session_factory)).get(
        "/v1/jobs", headers={"Origin": "http://localhost:5173"}
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_jobs_api_loads_provenance_and_metadata_in_batched_queries(
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
                source_position=0,
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
    assert len(statements) == 4
