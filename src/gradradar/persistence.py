from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gradradar.contracts import ParsedJobPosting
from gradradar.models import JobPosting, JobPostingSource, Source
from gradradar.source_config import SOURCES


def persist_posting(session: Session, posting: ParsedJobPosting, seen_at: datetime) -> JobPosting:
    source = session.scalar(select(Source).where(Source.name == posting.source_name))
    if source is None:
        raise ValueError(f"unknown source: {posting.source_name}")
    job = session.scalar(
        select(JobPosting).where(JobPosting.application_key == posting.application_key)
    )
    if job is None:
        job = JobPosting(
            application_key=posting.application_key,
            company_name=posting.company_name,
            title=posting.title,
            apply_url=str(posting.apply_url),
            location=posting.location,
            listed_at=posting.listed_at,
            first_seen_at=seen_at.astimezone(UTC),
        )
        session.add(job)
        session.flush()
    elif _priority(posting.source_name) < _display_priority(session, job):
        job.company_name, job.title = posting.company_name, posting.title
        job.apply_url, job.location, job.listed_at = (
            str(posting.apply_url),
            posting.location,
            posting.listed_at,
        )
    link = session.get(JobPostingSource, (job.id, source.id))
    if link is None:
        session.add(
            JobPostingSource(job_posting_id=job.id, source_id=source.id, last_seen_at=seen_at)
        )
    else:
        link.last_seen_at = seen_at
    return job


def _priority(name: str) -> int:
    return next(source.priority for source in SOURCES if source.name == name)


def _display_priority(session: Session, job: JobPosting) -> int:
    names = session.scalars(
        select(Source.name).join(JobPostingSource).where(JobPostingSource.job_posting_id == job.id)
    ).all()
    return min((_priority(name) for name in names), default=999)
