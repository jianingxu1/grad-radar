from datetime import UTC, datetime

from sqlalchemy import Connection, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPosting, JobPostingSource
from app.models.parsed_job_posting import ParsedJobPosting
from app.repositories.job_postings import persist_posting, persist_postings
from app.sources.bootstrap import bootstrap_sources
from app.sources.definitions import SourceName


def _posting(
    source_name: SourceName, company_name: str, posting_id: str = "123"
) -> ParsedJobPosting:
    return ParsedJobPosting(
        source_name=source_name,
        company_name=company_name,
        title="Software Engineer, New Grad",
        apply_url=f"https://jobs.example.com/postings/{posting_id}",
        application_key=f"https://jobs.example.com/postings/{posting_id}",
        location="San Francisco, CA",
        listed_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_position=0,
    )


def test_persistence_deduplicates_sources_and_keeps_higher_priority_display_fields(
    session_factory: sessionmaker[Session],
) -> None:
    first_seen = datetime(2026, 1, 2, tzinfo=UTC)
    with session_factory.begin() as session:
        assert bootstrap_sources(session) == 2
        job = persist_posting(
            session, _posting(SourceName.SPEEDYAPPLY, "SpeedyApply Co"), first_seen
        )
        job_id = job.id

    with session_factory.begin() as session:
        persist_posting(
            session,
            _posting(SourceName.SIMPLIFY, "Simplify Co"),
            datetime(2026, 1, 3, tzinfo=UTC),
        )

    with session_factory() as session:
        job = session.get(JobPosting, job_id)
        assert job is not None
        assert job.company_name == "Simplify Co"
        assert job.first_seen_at == first_seen
        assert session.scalar(select(func.count()).select_from(JobPosting)) == 1
        assert session.scalar(select(func.count()).select_from(JobPostingSource)) == 2
        assert {link.source_position for link in session.scalars(select(JobPostingSource))} == {0}


def test_persistence_refreshes_display_fields_from_the_current_primary_source(
    session_factory: sessionmaker[Session],
) -> None:
    first_seen = datetime(2026, 1, 2, tzinfo=UTC)
    with session_factory.begin() as session:
        assert bootstrap_sources(session) == 2
        job = persist_posting(
            session, _posting(SourceName.SIMPLIFY, "Old company name"), first_seen
        )
        job_id = job.id

    with session_factory.begin() as session:
        persist_posting(
            session,
            _posting(SourceName.SIMPLIFY, "Corrected company name"),
            datetime(2026, 1, 3, tzinfo=UTC),
        )

    with session_factory() as session:
        job = session.get(JobPosting, job_id)
        assert job is not None
        assert job.company_name == "Corrected company name"
        assert job.first_seen_at == first_seen


def test_batch_persistence_deduplicates_keys_and_preserves_source_priority(
    session_factory: sessionmaker[Session],
) -> None:
    first_seen = datetime(2026, 1, 2, tzinfo=UTC)
    with session_factory.begin() as session:
        assert bootstrap_sources(session) == 2
        jobs = persist_postings(
            session,
            [
                _posting(SourceName.SPEEDYAPPLY, "SpeedyApply Co"),
                _posting(SourceName.SIMPLIFY, "Simplify Co"),
                _posting(SourceName.SIMPLIFY, "Ignored duplicate"),
            ],
            first_seen,
        )
        assert len(jobs) == 3

    with session_factory() as session:
        job = session.scalar(select(JobPosting))
        assert job is not None
        assert job.company_name == "Simplify Co"
        assert job.first_seen_at == first_seen
        assert session.scalar(select(func.count()).select_from(JobPosting)) == 1
        assert session.scalar(select(func.count()).select_from(JobPostingSource)) == 2


def test_batch_persistence_uses_a_bounded_number_of_statements(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as session:
        assert bootstrap_sources(session) == 2

    with session_factory.begin() as session:
        statements: list[str] = []
        connection: Connection = session.connection()

        def count_statement(
            _connection: Connection,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            statements.append(statement)

        event.listen(connection, "before_cursor_execute", count_statement)
        try:
            persist_postings(
                session,
                [
                    _posting(SourceName.SIMPLIFY, f"Company {index}", str(index))
                    for index in range(25)
                ],
                datetime(2026, 1, 2, tzinfo=UTC),
            )
            session.flush()
        finally:
            event.remove(connection, "before_cursor_execute", count_statement)

    assert len(statements) <= 4
