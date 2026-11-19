"""Worker exclusivity uses independent, committed PostgreSQL connections."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, text
from sqlalchemy.orm import sessionmaker

from app.database.models import (
    JobPosting,
    NotificationDelivery,
    NotificationOutbox,
    TelegramConnection,
)
from app.services.notifications import deliver_pending
from app.services.telegram import TelegramClient, TelegramDelivery


@pytest.fixture
def queued_notification(integration_engine: Engine) -> Iterator[UUID]:
    now = datetime.now(UTC)
    user_id, job_id, connection_id, outbox_id = (uuid4() for _ in range(4))
    factory = sessionmaker(bind=integration_engine, expire_on_commit=False)
    with factory.begin() as session:
        session.execute(text("insert into auth.users (id) values (:id)"), {"id": user_id})
        session.add(
            JobPosting(
                id=job_id,
                application_key=str(job_id),
                company_name="Company",
                title="Software Engineer",
                apply_url="https://jobs.example.com/apply",
                location="USA",
                first_seen_at=now,
                listed_at=now,
            )
        )
        session.add(
            TelegramConnection(
                id=connection_id,
                user_id=user_id,
                telegram_user_id=202,
                telegram_chat_id=202,
                status="active",
                created_at=now,
                activated_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            NotificationOutbox(
                id=outbox_id,
                job_posting_id=job_id,
                telegram_connection_id=connection_id,
                ingestion_cycle_at=now,
                status="pending",
                attempts=0,
                next_attempt_at=now,
            )
        )
    try:
        yield outbox_id
    finally:
        with factory.begin() as session:
            session.execute(
                delete(NotificationDelivery).where(
                    NotificationDelivery.notification_outbox_id == outbox_id
                )
            )
            session.execute(delete(NotificationOutbox).where(NotificationOutbox.id == outbox_id))
            session.execute(
                delete(TelegramConnection).where(TelegramConnection.id == connection_id)
            )
            session.execute(delete(JobPosting).where(JobPosting.id == job_id))
            session.execute(text("delete from auth.users where id = :id"), {"id": user_id})


@pytest.mark.parametrize("fail_first", [False, True])
def test_only_one_delivery_pass_runs_and_lock_releases_after_transaction(
    integration_engine: Engine,
    queued_notification: UUID,
    fail_first: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    factory = sessionmaker(bind=integration_engine, expire_on_commit=False)
    now = datetime.now(UTC)
    sent = []

    class CompetingTelegram:
        def send_message(self, message: str, *, chat_id: str) -> TelegramDelivery:
            pytest.fail("Competing worker must not send a message")

    class FirstTelegram:
        def send_message(self, message: str, *, chat_id: str) -> TelegramDelivery:
            # This is a second physical connection while the first worker is in its HTTP call.
            with factory.begin() as competitor, caplog.at_level("INFO"):
                assert (
                    deliver_pending(competitor, cast(TelegramClient, CompetingTelegram()), now) == 0
                )
            assert "worker_already_running" in caplog.text
            sent.append(message)
            if fail_first:
                raise RuntimeError("worker crashed during send")
            return TelegramDelivery(True, message_id=42)

    def first_pass() -> None:
        with factory.begin() as session:
            assert deliver_pending(session, cast(TelegramClient, FirstTelegram()), now) == 1

    if fail_first:
        with pytest.raises(RuntimeError, match="worker crashed"):
            first_pass()
    else:
        first_pass()
    assert len(sent) == 1

    class NextTelegram:
        def send_message(self, message: str, *, chat_id: str) -> TelegramDelivery:
            sent.append(message)
            return TelegramDelivery(True, message_id=43)

    caplog.clear()
    with factory.begin() as session, caplog.at_level("INFO"):
        assert deliver_pending(session, cast(TelegramClient, NextTelegram()), now) == int(
            fail_first
        )
    assert "worker_already_running" not in caplog.text
    assert "notifications.delivery.started" in caplog.text
    assert len(sent) == (2 if fail_first else 1)
    with factory() as session:
        outbox = session.get(NotificationOutbox, queued_notification)
        assert outbox is not None
        assert outbox.status == "delivered"
