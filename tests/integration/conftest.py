from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def integration_engine() -> Iterator[Engine]:
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as container:
        engine = create_engine(container.get_connection_url(), pool_pre_ping=True)
        migrations = sorted((Path(__file__).parents[2] / "supabase" / "migrations").glob("*.sql"))
        with engine.begin() as connection:
            for migration in migrations:
                connection.exec_driver_sql(migration.read_text())
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def session_factory(integration_engine: Engine) -> Iterator[sessionmaker[Session]]:
    with integration_engine.connect() as connection:
        outer_transaction = connection.begin()
        test_factory = sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield test_factory
        finally:
            outer_transaction.rollback()
