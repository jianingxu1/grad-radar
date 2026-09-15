"""Private Telegram connection and database-backed delivery workflow."""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

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

TOKEN_TTL = timedelta(minutes=10)
TELEGRAM_MESSAGE_LIMIT = 4096


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
        return connection.status if connection.status != "blocked" else "disabled", None
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
) -> bool:
    if not token or len(token) > 64:
        return False
    intent = session.scalar(
        select(TelegramLinkIntent)
        .where(TelegramLinkIntent.token_hash == _token_hash(token))
        .with_for_update()
    )
    if not intent or intent.consumed_at or intent.expires_at <= now:
        return False
    existing_chat = session.scalar(
        select(TelegramConnection).where(TelegramConnection.telegram_chat_id == telegram_chat_id)
    )
    existing_user = session.scalar(
        select(TelegramConnection).where(TelegramConnection.user_id == intent.user_id)
    )
    if existing_chat or existing_user:
        return False
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
    return True


def enqueue_new_jobs(session: Session, job_ids: list[UUID], cycle_at: datetime) -> int:
    if not job_ids:
        return 0
    connections = session.scalars(
        select(TelegramConnection).where(
            TelegramConnection.status == "active", TelegramConnection.activated_at < cycle_at
        )
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
        for job_id in job_ids
        for connection in connections
    ]
    if not rows:
        return 0
    session.execute(
        insert(NotificationOutbox)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=[
                NotificationOutbox.job_posting_id,
                NotificationOutbox.telegram_connection_id,
            ]
        )
    )
    return len(rows)


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
                delivered += len(message_outbox_rows)
                continue
            _record_failure(message_outbox_rows, connection, outcome, now)
            break
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
    messages: list[tuple[str, list[JobPosting]]] = []
    current = "New GradRadar jobs:\n"
    current_jobs: list[JobPosting] = []
    for job in jobs:
        line = f"{job.company_name} — {job.title}\n{job.location}\n{job.apply_url}"
        candidate = (
            f"{current}\n\n{line}" if current != "New GradRadar jobs:\n" else f"{current}{line}"
        )
        if len(candidate) > TELEGRAM_MESSAGE_LIMIT and current != "New GradRadar jobs:\n":
            messages.append((current, current_jobs))
            current = f"New GradRadar jobs (continued):\n{line}"
            current_jobs = [job]
        else:
            current = candidate
            current_jobs.append(job)
    if current.strip():
        messages.append((current, current_jobs))
    return messages


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
