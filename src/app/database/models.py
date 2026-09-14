from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue, ForeignKey, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="public")


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    application_key: Mapped[str] = mapped_column(String, unique=True)
    company_name: Mapped[str]
    title: Mapped[str]
    apply_url: Mapped[str]
    location: Mapped[str]
    listed_at: Mapped[datetime | None]
    first_seen_at: Mapped[datetime]


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    name: Mapped[str] = mapped_column(String, unique=True)
    url: Mapped[str]
    last_processed_revision_sha: Mapped[str | None]
    last_successful_sync_at: Mapped[datetime | None]


class JobPostingSource(Base):
    __tablename__ = "job_posting_sources"

    job_posting_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="RESTRICT"), primary_key=True
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), primary_key=True
    )
    last_seen_at: Mapped[datetime]
    source_position: Mapped[int | None]
