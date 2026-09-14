from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings, get_settings


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    database_url = str(settings.database_url).replace("postgresql://", "postgresql+psycopg://", 1)
    engine: Engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
    )
    return sessionmaker(bind=engine, expire_on_commit=False)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return create_session_factory(get_settings())


@contextmanager
def transaction(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        with session.begin():
            yield session
    finally:
        session.close()
