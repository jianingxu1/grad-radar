from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy.orm import Session, sessionmaker

from app import cli


class FakeSession:
    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *_: object) -> None:
        pass


def test_ingest_and_deliver_sends_pending_notifications_after_ingestion(
    monkeypatch: Any,
) -> None:
    session = FakeSession()
    session_factory = cast(sessionmaker[Session], SimpleNamespace(begin=lambda: session))
    summaries = [SimpleNamespace(status="success")]
    calls: list[tuple[str, Any]] = []

    class FakeTelegramClient:
        def __init__(self, token: str | None) -> None:
            calls.append(("token", token))

        def __enter__(self) -> "FakeTelegramClient":
            return self

        def __exit__(self, *_: object) -> None:
            pass

    def fake_ingest(factory: object, token: str | None) -> list[SimpleNamespace]:
        calls.append(("ingest", (factory, token)))
        return summaries

    def fake_deliver(delivery_session: object, telegram: object, now: datetime) -> None:
        calls.append(("deliver", (delivery_session, telegram, now)))

    monkeypatch.setattr(cli, "TelegramClient", FakeTelegramClient)
    monkeypatch.setattr(cli, "ingest_all", fake_ingest)
    monkeypatch.setattr(cli, "deliver_pending", fake_deliver)

    assert cli.ingest_and_deliver(session_factory, "github-token", "telegram-token") is summaries
    assert calls[0] == ("ingest", (session_factory, "github-token"))
    assert calls[1] == ("token", "telegram-token")
    assert calls[2][0] == "deliver"
    assert calls[2][1][0] is session
    assert isinstance(calls[2][1][2], datetime)
    assert calls[2][1][2].tzinfo is UTC
