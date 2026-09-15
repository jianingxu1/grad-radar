from collections.abc import Callable
from typing import Any, cast

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy.orm import Session, sessionmaker

from app.scheduler import SCHEDULER_TIMEZONE, configure_scheduler, run_scheduled_ingestion


class FakeScheduler:
    def __init__(self) -> None:
        self.jobs: list[tuple[Callable[[], None], dict[str, Any]]] = []

    def add_job(self, func: Callable[[], None], **kwargs: object) -> None:
        self.jobs.append((func, kwargs))

    def start(self) -> None:
        pass


class LockingSession:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.executed: list[str] = []

    def __enter__(self) -> "LockingSession":
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def scalar(self, statement: object, params: object) -> bool:
        return self.acquired

    def execute(self, statement: object, params: object) -> None:
        self.executed.append(str(statement))


def test_scheduler_registers_ingestion_and_minute_delivery_jobs() -> None:
    scheduler = FakeScheduler()

    configure_scheduler(
        cast(BlockingScheduler, scheduler),
        session_factory=cast(sessionmaker[Session], object()),
        github_token=None,
    )

    assert len(scheduler.jobs) == 3
    daytime = scheduler.jobs[0][1]
    overnight = scheduler.jobs[1][1]
    delivery = scheduler.jobs[2][1]
    assert str(daytime["trigger"]) == "cron[hour='7-20', minute='*/15']"
    assert str(overnight["trigger"]) == "cron[hour='1,3,5,21,23', minute='0']"
    assert daytime["trigger"].timezone == SCHEDULER_TIMEZONE
    assert overnight["trigger"].timezone == SCHEDULER_TIMEZONE
    assert str(delivery["trigger"]) == "cron[minute='*']"
    assert delivery["trigger"].timezone == SCHEDULER_TIMEZONE
    assert daytime["max_instances"] == 1
    assert daytime["coalesce"] is True
    assert daytime["misfire_grace_time"] == 300


def test_running_scheduler_skips_when_another_worker_holds_the_lock(monkeypatch: Any) -> None:
    session = LockingSession(acquired=False)
    session_factory = cast(sessionmaker[Session], lambda: session)
    called = False

    def fake_ingest(*args: object) -> list[object]:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr("app.scheduler.ingest_all", fake_ingest)

    assert run_scheduled_ingestion(session_factory, github_token=None) is None
    assert called is False
    assert session.executed == []
