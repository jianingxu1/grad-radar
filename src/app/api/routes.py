from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.schemas import JobPageResponse, JobResponse, SourceResponse
from app.database.models import JobPosting, JobPostingSource, Source
from app.database.session import get_session_factory


def create_router(session_factory: sessionmaker[Session] | None = None) -> APIRouter:
    router = APIRouter()

    def get_session() -> Iterator[Session]:
        factory = get_session_factory() if session_factory is None else session_factory
        with factory() as session:
            yield session

    @router.get("/v1/jobs", response_model=JobPageResponse)
    def list_jobs(
        *,
        q: str | None = None,
        location: str | None = None,
        remote: bool | None = None,
        company: str | None = None,
        posted_within_hours: Annotated[int | None, Query(ge=1)] = None,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        session: Annotated[Session, Depends(get_session)],
    ) -> JobPageResponse:
        statement: Select[tuple[JobPosting]] = select(JobPosting)
        if q:
            pattern = f"%{q.strip()}%"
            statement = statement.where(
                or_(JobPosting.company_name.ilike(pattern), JobPosting.title.ilike(pattern))
            )
        if location:
            statement = statement.where(JobPosting.location.ilike(f"%{location.strip()}%"))
        if remote is not None:
            has_remote = JobPosting.location.ilike("%remote%")
            statement = statement.where(has_remote if remote else ~has_remote)
        if company:
            statement = statement.where(JobPosting.company_name.ilike(f"%{company.strip()}%"))
        if posted_within_hours:
            statement = statement.where(
                JobPosting.first_seen_at >= datetime.now(UTC) - timedelta(hours=posted_within_hours)
            )
        jobs = session.scalars(
            statement.order_by(JobPosting.listed_at.desc().nulls_last(), JobPosting.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        sources_by_job = _sources_by_job(session, [job.id for job in jobs])
        return JobPageResponse(
            items=[_job_response(job, sources_by_job[job.id]) for job in jobs],
            offset=offset,
            limit=limit,
        )

    return router


def _sources_by_job(session: Session, job_ids: list[UUID]) -> dict[UUID, list[SourceResponse]]:
    sources_by_job: dict[UUID, list[SourceResponse]] = defaultdict(list)
    if not job_ids:
        return sources_by_job
    rows = session.execute(
        select(JobPostingSource.job_posting_id, Source.name, Source.url)
        .join(JobPostingSource, JobPostingSource.source_id == Source.id)
        .where(JobPostingSource.job_posting_id.in_(job_ids))
        .order_by(JobPostingSource.job_posting_id, Source.name)
    ).all()
    for job_id, name, url in rows:
        sources_by_job[job_id].append(SourceResponse(name=name, url=url))
    return sources_by_job


def _job_response(job: JobPosting, sources: list[SourceResponse]) -> JobResponse:
    return JobResponse(
        id=job.id,
        company_name=job.company_name,
        title=job.title,
        apply_url=job.apply_url,
        location=job.location,
        listed_at=job.listed_at,
        first_seen_at=job.first_seen_at,
        sources=sources,
    )
