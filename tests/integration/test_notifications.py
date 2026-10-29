from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPosting, NotificationOutbox, TelegramConnection
from app.services.notifications import (
    connection_state,
    consume_start,
    create_link_intent,
    disable_connection,
    enqueue_new_jobs,
)


def _create_auth_user(session: Session) -> UUID:
    user_id = uuid4()
    session.execute(text("insert into auth.users (id) values (:id)"), {"id": user_id})
    return user_id


def test_disabled_connection_can_reconnect_with_the_same_private_chat(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory.begin() as session:
        user_id = _create_auth_user(session)
        token, _ = create_link_intent(session, user_id, now)
        assert consume_start(session, token, 101, 202, now) == "connected"
        assert disable_connection(session, user_id, now + timedelta(minutes=1))
        reconnect_token, _ = create_link_intent(session, user_id, now + timedelta(minutes=2))
        assert (
            consume_start(session, reconnect_token, 101, 202, now + timedelta(minutes=2))
            == "connected"
        )

    with session_factory() as session:
        connections = session.scalars(select(TelegramConnection)).all()
        assert len(connections) == 1
        assert connections[0].status == "active"
        assert connection_state(session, user_id, now)[0] == "connected"


def test_start_link_accepts_telegram_ids_larger_than_a_postgres_integer(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    telegram_user_id = 7_773_528_773
    telegram_chat_id = 7_773_528_773
    with session_factory.begin() as session:
        user_id = _create_auth_user(session)
        token, _ = create_link_intent(session, user_id, now)

        assert consume_start(session, token, telegram_user_id, telegram_chat_id, now) == "connected"

    with session_factory() as session:
        connection = session.scalar(select(TelegramConnection))
        assert connection is not None
        assert connection.telegram_user_id == telegram_user_id
        assert connection.telegram_chat_id == telegram_chat_id


def test_start_link_reports_telegram_user_conflict_before_insert(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory.begin() as session:
        first_user_id = _create_auth_user(session)
        second_user_id = _create_auth_user(session)
        session.add(
            TelegramConnection(
                user_id=first_user_id,
                telegram_user_id=101,
                telegram_chat_id=202,
                status="active",
                created_at=now,
                activated_at=now,
                disabled_at=None,
                updated_at=now,
            )
        )
        token, _ = create_link_intent(session, second_user_id, now)
        assert consume_start(session, token, 101, 303, now) == "telegram_user_conflict"


def test_enqueue_requires_posting_dates_to_be_newer_than_connection_activation(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory.begin() as session:
        user_id = _create_auth_user(session)
        old_job = JobPosting(
            application_key="old",
            company_name="Old",
            title="New Grad",
            apply_url="https://old",
            location="USA",
            listed_at=now,
            first_seen_at=now,
        )
        new_job = JobPosting(
            application_key="new",
            company_name="New",
            title="New Grad",
            apply_url="https://new",
            location="USA",
            listed_at=now + timedelta(minutes=2),
            first_seen_at=now + timedelta(minutes=2),
        )
        old_listing = JobPosting(
            application_key="old-listing",
            company_name="Old listing",
            title="New Grad",
            apply_url="https://old-listing",
            location="USA",
            listed_at=now,
            first_seen_at=now + timedelta(minutes=2),
        )
        no_listed_date = JobPosting(
            application_key="no-listed-date",
            company_name="No listed date",
            title="New Grad",
            apply_url="https://no-listed-date",
            location="USA",
            listed_at=None,
            first_seen_at=now + timedelta(minutes=2),
        )
        equal_dates = JobPosting(
            application_key="equal-dates",
            company_name="Equal dates",
            title="New Grad",
            apply_url="https://equal-dates",
            location="USA",
            listed_at=now + timedelta(minutes=1),
            first_seen_at=now + timedelta(minutes=1),
        )
        session.add_all([old_job, new_job, old_listing, no_listed_date, equal_dates])
        session.flush()
        session.add(
            TelegramConnection(
                user_id=user_id,
                telegram_user_id=101,
                telegram_chat_id=202,
                status="active",
                created_at=now + timedelta(minutes=1),
                activated_at=now + timedelta(minutes=1),
                disabled_at=None,
                updated_at=now + timedelta(minutes=1),
            )
        )
        session.flush()
        assert (
            enqueue_new_jobs(
                session,
                [old_job.id, new_job.id, old_listing.id, no_listed_date.id, equal_dates.id],
                now,
            )
            == 3
        )

    with session_factory() as session:
        outbox = session.scalars(select(NotificationOutbox)).all()
        assert {row.job_posting_id for row in outbox} == {
            new_job.id,
            no_listed_date.id,
            equal_dates.id,
        }
