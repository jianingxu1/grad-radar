from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue, ForeignKey, MetaData, String, Text
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


class TelegramLinkIntent(Base):
    __tablename__ = "telegram_link_intents"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    token_hash: Mapped[str] = mapped_column(String)
    user_id: Mapped[UUID]
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    consumed_at: Mapped[datetime | None]


class TelegramConnection(Base):
    __tablename__ = "telegram_connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    user_id: Mapped[UUID]
    telegram_user_id: Mapped[int] = mapped_column(unique=True)
    telegram_chat_id: Mapped[int] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime]
    activated_at: Mapped[datetime | None]
    disabled_at: Mapped[datetime | None]
    updated_at: Mapped[datetime]


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    job_posting_id: Mapped[UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="RESTRICT"))
    telegram_connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("telegram_connections.id", ondelete="RESTRICT")
    )
    ingestion_cycle_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(String)
    attempts: Mapped[int]
    next_attempt_at: Mapped[datetime]
    locked_at: Mapped[datetime | None]
    delivered_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    notification_outbox_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_outbox.id", ondelete="RESTRICT")
    )
    attempted_at: Mapped[datetime]
    telegram_message_id: Mapped[int | None]
    success: Mapped[bool]
    error: Mapped[str | None] = mapped_column(Text)
