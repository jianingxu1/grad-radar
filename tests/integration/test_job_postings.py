from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPosting, JobPostingSource
from app.models.parsed_job_posting import ParsedJobPosting
from app.repositories.job_postings import persist_posting
from app.sources.bootstrap import bootstrap_sources
from app.sources.definitions import SourceName


def _posting(source_name: SourceName, company_name: str) -> ParsedJobPosting:
    return ParsedJobPosting(
        source_name=source_name,
        company_name=company_name,
        title="Software Engineer, New Grad",
        apply_url="https://jobs.example.com/postings/123",
        application_key="https://jobs.example.com/postings/123",
        location="San Francisco, CA",
        listed_at=datetime(2026, 1, 1, tzinfo=UTC),
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
