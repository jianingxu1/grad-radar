"""Private Telegram connection and database-backed delivery workflow."""

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta
from html import escape
from typing import Literal
from uuid import UUID

from bs4 import BeautifulSoup
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database.models import (
    JobPosting,
    NotificationDelivery,
    NotificationOutbox,
    TelegramConnection,
    TelegramLinkIntent,
)
from app.services.telegram import TelegramClient, TelegramDelivery

logger = logging.getLogger(__name__)

TOKEN_TTL = timedelta(minutes=10)
TELEGRAM_MESSAGE_LIMIT = 4096
_MAX_DISPLAY_FIELD_LENGTH = 512
_TRACKER_HTML_TAG = re.compile(r"</?(?:a|b|em|i|span|strong)\b", re.IGNORECASE)
StartConsumeResult = Literal[
    "connected",
    "already_connected",
    "expired_or_used",
    "invalid",
    "chat_conflict",
    "telegram_user_conflict",
    "user_conflict",
]


def create_link_intent(session: Session, user_id: UUID, now: datetime) -> tuple[str, datetime]:
    session.execute(
        update(TelegramLinkIntent)
        .where(TelegramLinkIntent.user_id == user_id, TelegramLinkIntent.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    token = secrets.token_urlsafe(32)
    expires_at = now + TOKEN_TTL
    session.add(
        TelegramLinkIntent(
            token_hash=_token_hash(token), user_id=user_id, created_at=now, expires_at=expires_at
        )
    )
    return token, expires_at


def connection_state(session: Session, user_id: UUID, now: datetime) -> tuple[str, datetime | None]:
    connection = session.scalar(
        select(TelegramConnection).where(TelegramConnection.user_id == user_id)
    )
    if connection:
        return "connected" if connection.status == "active" else "disabled", None
    intent = session.scalar(
        select(TelegramLinkIntent)
        .where(
            TelegramLinkIntent.user_id == user_id,
            TelegramLinkIntent.consumed_at.is_(None),
            TelegramLinkIntent.expires_at > now,
        )
        .order_by(TelegramLinkIntent.created_at.desc())
    )
    return ("pending", intent.expires_at) if intent else ("not_connected", None)


def disable_connection(session: Session, user_id: UUID, now: datetime) -> bool:
    connection = session.scalar(
        select(TelegramConnection).where(TelegramConnection.user_id == user_id)
    )
    if not connection:
        return False
    connection.status, connection.disabled_at, connection.updated_at = "disabled", now, now
    session.execute(
        update(NotificationOutbox)
        .where(
            NotificationOutbox.telegram_connection_id == connection.id,
            NotificationOutbox.status == "pending",
        )
        .values(status="cancelled", last_error="Telegram alerts disconnected")
    )
    return True


def consume_start(
    session: Session, token: str, telegram_user_id: int, telegram_chat_id: int, now: datetime
) -> StartConsumeResult:
    if not token or len(token) > 64:
        return "invalid"
    intent = session.scalar(
        select(TelegramLinkIntent)
        .where(TelegramLinkIntent.token_hash == _token_hash(token))
        .with_for_update()
    )
    if not intent or intent.consumed_at or intent.expires_at <= now:
        return "expired_or_used"
    existing_chat = session.scalar(
        select(TelegramConnection).where(TelegramConnection.telegram_chat_id == telegram_chat_id)
    )
    existing_user = session.scalar(
        select(TelegramConnection).where(TelegramConnection.user_id == intent.user_id)
    )
    existing_telegram_user = session.scalar(
        select(TelegramConnection).where(TelegramConnection.telegram_user_id == telegram_user_id)
    )
    if existing_chat and existing_chat is not existing_user:
        return "chat_conflict"
    if existing_telegram_user and existing_telegram_user is not existing_user:
        return "telegram_user_conflict"
    connection = existing_user or existing_chat
    if connection:
        if connection.user_id != intent.user_id or connection.telegram_user_id != telegram_user_id:
            return "user_conflict"
        if connection.status == "active":
            return "already_connected"
        connection.telegram_chat_id = telegram_chat_id
        connection.status = "active"
        connection.activated_at = now
        connection.disabled_at = None
        connection.updated_at = now
        intent.consumed_at = now
        return "connected"
    intent.consumed_at = now
    session.add(
        TelegramConnection(
            user_id=intent.user_id,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            status="active",
            created_at=now,
            activated_at=now,
            updated_at=now,
        )
    )
    return "connected"


def enqueue_new_jobs(session: Session, job_ids: list[UUID], cycle_at: datetime) -> int:
    if not job_ids:
        return 0
    jobs = session.execute(
        select(JobPosting.id, JobPosting.first_seen_at).where(JobPosting.id.in_(job_ids))
    ).all()
    connections = session.scalars(
        select(TelegramConnection).where(TelegramConnection.status == "active")
    ).all()
    rows = [
        {
            "job_posting_id": job_id,
            "telegram_connection_id": connection.id,
            "ingestion_cycle_at": cycle_at,
            "status": "pending",
            "attempts": 0,
            "next_attempt_at": cycle_at,
        }
        for job_id, first_seen_at in jobs
        for connection in connections
        if connection.activated_at is not None and connection.activated_at < first_seen_at
    ]
    if not rows:
        logger.info("notifications.enqueue.completed new_jobs=%s enqueued=0", len(job_ids))
        return 0
    inserted_rows = session.execute(
        insert(NotificationOutbox)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=[
                NotificationOutbox.job_posting_id,
                NotificationOutbox.telegram_connection_id,
            ]
        )
        .returning(NotificationOutbox.id)
    ).all()
    logger.info(
        "notifications.enqueue.completed new_jobs=%s active_connections=%s enqueued=%s",
        len(job_ids),
        len(connections),
        len(inserted_rows),
    )
    return len(inserted_rows)


def deliver_pending(session: Session, telegram: TelegramClient, now: datetime) -> int:
    rows = (
        session.execute(
            select(NotificationOutbox, TelegramConnection, JobPosting)
            .join(
                TelegramConnection,
                NotificationOutbox.telegram_connection_id == TelegramConnection.id,
            )
            .join(JobPosting, NotificationOutbox.job_posting_id == JobPosting.id)
            .where(
                NotificationOutbox.status == "pending",
                NotificationOutbox.next_attempt_at <= now,
                TelegramConnection.status == "active",
            )
            .order_by(
                NotificationOutbox.telegram_connection_id, NotificationOutbox.ingestion_cycle_at
            )
            .with_for_update(skip_locked=True)
        )
        .tuples()
        .all()
    )
    groups: dict[
        tuple[UUID, datetime], list[tuple[NotificationOutbox, TelegramConnection, JobPosting]]
    ] = {}
    for row in rows:
        groups.setdefault((row[0].telegram_connection_id, row[0].ingestion_cycle_at), []).append(
            row
        )
    delivered = 0
    logger.info(
        "notifications.delivery.started pending=%s batches=%s",
        len(rows),
        sum(len(_message_batches([row[2] for row in group])) for group in groups.values()),
    )
    for _, group in groups.items():
        outbox_rows = [row[0] for row in group]
        connection = group[0][1]
        jobs = [row[2] for row in group]
        outbox_by_job = {outbox.job_posting_id: outbox for outbox in outbox_rows}
        for message, message_jobs in _message_batches(jobs):
            message_outbox_rows = [outbox_by_job[job.id] for job in message_jobs]
            outcome = telegram.send_message(message, chat_id=str(connection.telegram_chat_id))
            for outbox in message_outbox_rows:
                session.add(
                    NotificationDelivery(
                        notification_outbox_id=outbox.id,
                        attempted_at=now,
                        telegram_message_id=outcome.message_id,
                        success=outcome.success,
                        error=outcome.error,
                    )
                )
            if outcome.success:
                for outbox in message_outbox_rows:
                    outbox.status, outbox.delivered_at, outbox.locked_at = "delivered", now, None
                    delivered += 1
                logger.info(
                    "notifications.delivery.succeeded jobs=%s message_id=%s",
                    len(message_outbox_rows),
                    outcome.message_id,
                )
                continue
            _record_failure(message_outbox_rows, connection, outcome, now)
            logger.error(
                "notifications.delivery.failed jobs=%s error=%s status_code=%s "
                "retry_after=%s blocked=%s",
                len(message_outbox_rows),
                outcome.error,
                outcome.status_code,
                outcome.retry_after,
                connection.status == "blocked",
            )
            break
    logger.info(
        "notifications.delivery.completed pending=%s delivered=%s failed_or_deferred=%s",
        len(rows),
        delivered,
        len(rows) - delivered,
    )
    return delivered


def _record_failure(
    rows: list[NotificationOutbox],
    connection: TelegramConnection,
    outcome: TelegramDelivery,
    now: datetime,
) -> None:
    blocked = outcome.status_code == 403 or (
        outcome.error
        and ("blocked" in outcome.error.lower() or "forbidden" in outcome.error.lower())
    )
    if blocked:
        connection.status, connection.disabled_at, connection.updated_at = "blocked", now, now
    for row in rows:
        row.attempts += 1
        row.last_error, row.locked_at = outcome.error, None
        if blocked or row.attempts >= 8:
            row.status = "failed"
        else:
            delay = outcome.retry_after or min(2**row.attempts * 60, 3600)
            row.next_attempt_at = now + timedelta(seconds=delay)


def _message_batches(jobs: list[JobPosting]) -> list[tuple[str, list[JobPosting]]]:
    batches: list[list[JobPosting]] = []
    current_jobs: list[JobPosting] = []
    for job in jobs:
        candidate_jobs = [*current_jobs, job]
        if len(_render_message(candidate_jobs)) > TELEGRAM_MESSAGE_LIMIT and current_jobs:
            batches.append(current_jobs)
            current_jobs = [job]
        else:
            current_jobs = candidate_jobs
    if current_jobs:
        batches.append(current_jobs)
    return [(_render_message(batch), batch) for batch in batches]


def _render_message(jobs: list[JobPosting]) -> str:
    count = len(jobs)
    noun = "job" if count == 1 else "jobs"
    return f"🔔 {count} new {noun} found\n\n" + "\n\n──────────────\n\n".join(
        _job_line(job) for job in jobs
    )


def _job_line(job: JobPosting) -> str:
    company = _escape_html(job.company_name, _MAX_DISPLAY_FIELD_LENGTH)
    title = _escape_html(job.title, _MAX_DISPLAY_FIELD_LENGTH)
    location = _escape_html(job.location, _MAX_DISPLAY_FIELD_LENGTH)
    prefix = f"<b>{company}</b>\n💼 {title}\n📍 {location}\n"
    apply_url = _escape_html(
        job.apply_url,
        TELEGRAM_MESSAGE_LIMIT - len(prefix) - len('<a href="">Apply</a>'),
        quote=True,
    )
    return f'{prefix}🔗 <a href="{apply_url}">Apply</a>'


def _escape_html(value: str, limit: int, *, quote: bool = False) -> str:
    plain_text = (
        BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
        if _TRACKER_HTML_TAG.search(value)
        else value
    )
    escaped = escape(plain_text, quote=quote)
    if len(escaped) <= limit:
        return escaped
    truncated = ""
    for character in plain_text:
        candidate = escape(f"{truncated}{character}…", quote=quote)
        if len(candidate) > limit:
            break
        truncated += character
    return escape(f"{truncated}…", quote=quote)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
