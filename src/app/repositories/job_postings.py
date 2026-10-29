from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database.models import JobPosting, JobPostingSource, Source
from app.models.parsed_job_posting import ParsedJobPosting


def persist_posting(session: Session, posting: ParsedJobPosting, seen_at: datetime) -> JobPosting:
    return persist_postings(session, [posting], seen_at)[0]


def persist_postings(
    session: Session, postings: Iterable[ParsedJobPosting], seen_at: datetime
) -> list[JobPosting]:
    """Persist a source revision with a bounded number of database round trips."""
    posting_list = list(postings)
    if not posting_list:
        return []

    unique_postings: dict[tuple[str, str], ParsedJobPosting] = {}
    for posting in posting_list:
        unique_postings.setdefault((posting.application_key, str(posting.source_name)), posting)

    source_names = {str(posting.source_name) for posting in unique_postings.values()}
    sources = {
        source.name: source
        for source in session.scalars(select(Source).where(Source.name.in_(source_names)))
    }
    missing_sources = source_names - sources.keys()
    if missing_sources:
        raise ValueError(f"unknown sources: {', '.join(sorted(missing_sources))}")
    priorities = {name: source.priority for name, source in sources.items()}

    application_keys = {posting.application_key for posting in unique_postings.values()}
    jobs_by_key = {
        job.application_key: job
        for job in session.scalars(
            select(JobPosting).where(JobPosting.application_key.in_(application_keys))
        )
    }
    source_names_by_key = {key: set[str]() for key in application_keys}
    if jobs_by_key:
        existing_sources = session.execute(
            select(JobPosting.application_key, Source.name, Source.priority)
            .join(JobPostingSource, JobPostingSource.job_posting_id == JobPosting.id)
            .join(Source, JobPostingSource.source_id == Source.id)
            .where(JobPosting.application_key.in_(jobs_by_key))
        )
        for application_key, source_name, priority in existing_sources:
            source_names_by_key[application_key].add(source_name)
            priorities[source_name] = priority

    new_postings_by_key: dict[str, ParsedJobPosting] = {}
    for posting in unique_postings.values():
        job = jobs_by_key.get(posting.application_key)
        known_sources = source_names_by_key[posting.application_key]
        if job is None:
            current_posting = new_postings_by_key.get(posting.application_key)
            if (
                current_posting is None
                or priorities[posting.source_name] < priorities[current_posting.source_name]
            ):
                new_postings_by_key[posting.application_key] = posting
        elif priorities[posting.source_name] <= _display_priority(known_sources, priorities):
            job.company_name, job.title = posting.company_name, posting.title
            job.apply_url, job.location, job.listed_at = (
                str(posting.apply_url),
                posting.location,
                posting.listed_at,
            )
        known_sources.add(str(posting.source_name))

    if new_postings_by_key:
        inserted_jobs = session.scalars(
            insert(JobPosting).returning(JobPosting),
            [
                {
                    "application_key": posting.application_key,
                    "company_name": posting.company_name,
                    "title": posting.title,
                    "apply_url": str(posting.apply_url),
                    "location": posting.location,
                    "listed_at": posting.listed_at,
                    "first_seen_at": seen_at.astimezone(UTC),
                }
                for posting in new_postings_by_key.values()
            ],
        ).all()
        jobs_by_key.update({job.application_key: job for job in inserted_jobs})

    link_rows = [
        {
            "job_posting_id": jobs_by_key[posting.application_key].id,
            "source_id": sources[str(posting.source_name)].id,
            "last_seen_at": seen_at,
            "source_position": posting.source_position,
            "active": True,
        }
        for posting in unique_postings.values()
    ]
    link_insert = insert(JobPostingSource).values(link_rows)
    session.execute(
        link_insert.on_conflict_do_update(
            index_elements=[JobPostingSource.job_posting_id, JobPostingSource.source_id],
            set_={
                "last_seen_at": link_insert.excluded.last_seen_at,
                "source_position": link_insert.excluded.source_position,
                "active": True,
            },
        )
    )

    return [jobs_by_key[posting.application_key] for posting in posting_list]


def persist_postings_with_new_ids(
    session: Session, postings: Iterable[ParsedJobPosting], seen_at: datetime
) -> tuple[list[JobPosting], list[UUID]]:
    """Persist postings and expose the IDs created in this ingestion cycle."""
    posting_list = list(postings)
    application_keys = {posting.application_key for posting in posting_list}
    known_keys = set(
        session.scalars(
            select(JobPosting.application_key).where(
                JobPosting.application_key.in_(application_keys)
            )
        )
    )
    jobs = persist_postings(session, posting_list, seen_at)
    return jobs, list({job.id for job in jobs if job.application_key not in known_keys})


def _display_priority(source_names: set[str], priorities: dict[str, int]) -> int:
    return min((priorities.get(name, 999) for name in source_names), default=999)
