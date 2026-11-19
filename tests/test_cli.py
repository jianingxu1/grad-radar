from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app import cli


def test_ingestion_queues_jobs_without_delivering(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = MagicMock()
    summaries = [SimpleNamespace(status="success")]
    ingest = MagicMock(return_value=summaries)
    monkeypatch.setattr(cli, "ingest_all", ingest)
    monkeypatch.setattr(cli, "ingest_all_boards", MagicMock(return_value=[("board", "success")]))
    monkeypatch.setattr(cli, "bootstrap_seed_boards", MagicMock())
    deliver = MagicMock()
    telegram = MagicMock()
    monkeypatch.setattr(cli, "deliver_pending", deliver)
    monkeypatch.setattr(cli, "TelegramClient", telegram)

    result = cli.run_ingestion(factory, "github-token")

    assert result is summaries
    assert len(result) == 2
    ingest.assert_called_once_with(factory, "github-token")
    deliver.assert_not_called()
    telegram.assert_not_called()


def test_notification_delivery_runs_once_in_a_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = MagicMock()
    session = factory.begin.return_value.__enter__.return_value
    telegram_context = MagicMock()
    telegram = telegram_context.__enter__.return_value
    client = MagicMock(return_value=telegram_context)
    deliver = MagicMock(return_value=3)
    monkeypatch.setattr(cli, "TelegramClient", client)
    monkeypatch.setattr(cli, "deliver_pending", deliver)

    assert cli.run_notification_delivery(factory, "telegram-token") == 3

    client.assert_called_once_with("telegram-token")
    delivery_session, delivery_client, attempted_at = deliver.call_args.args
    assert delivery_session is session
    assert delivery_client is telegram
    assert isinstance(attempted_at, datetime)
    assert attempted_at.tzinfo is UTC
    deliver.assert_called_once()
    factory.begin.return_value.__exit__.assert_called_once_with(None, None, None)
    telegram_context.__exit__.assert_called_once_with(None, None, None)


def test_notification_delivery_failure_leaves_transaction_with_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = MagicMock()
    client = MagicMock()
    monkeypatch.setattr(cli, "TelegramClient", client)
    monkeypatch.setattr(cli, "deliver_pending", MagicMock(side_effect=RuntimeError("failed")))

    with pytest.raises(RuntimeError, match="failed"):
        cli.run_notification_delivery(factory, "telegram-token")

    assert factory.begin.return_value.__exit__.call_args.args[0] is RuntimeError
    assert client.return_value.__exit__.call_args.args[0] is RuntimeError


@pytest.mark.parametrize("fails", [False, True])
def test_delivery_command_routes_and_disposes_database_engine(
    monkeypatch: pytest.MonkeyPatch, fails: bool
) -> None:
    settings = SimpleNamespace(log_level="INFO", telegram_bot_token="telegram-token")
    engine = MagicMock()
    factory = cast(sessionmaker[Session], SimpleNamespace(kw={"bind": engine}))
    run = MagicMock(side_effect=RuntimeError("failed") if fails else None)
    monkeypatch.setattr("sys.argv", ["gradradar", "deliver-notifications"])
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "create_session_factory", lambda _: factory)
    monkeypatch.setattr(cli, "run_notification_delivery", run)

    if fails:
        with pytest.raises(RuntimeError, match="failed"):
            cli.main()
    else:
        cli.main()

    run.assert_called_once_with(factory, "telegram-token")
    engine.dispose.assert_called_once()


def test_delivery_command_requires_token_before_opening_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = SimpleNamespace(log_level="INFO", telegram_bot_token=None)
    factory = MagicMock()
    monkeypatch.setattr("sys.argv", ["gradradar", "deliver-notifications"])
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "create_session_factory", factory)

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert "TELEGRAM_BOT_TOKEN is required" in capsys.readouterr().err
    factory.assert_not_called()
