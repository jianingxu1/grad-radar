from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Source
from app.sources.board_filter import DEFAULT_FILTER
from app.sources.seed_boards import (
    LEGACY_DEFAULT_FILTERS,
    PREVIOUS_DEFAULT_FILTER,
    bootstrap_seed_boards,
)


def test_seed_boards_are_idempotent_and_do_not_reenable_disabled_sources(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as session:
        assert bootstrap_seed_boards(session) == 9
    with session_factory.begin() as session:
        source = session.scalar(select(Source).where(Source.name == "greenhouse:stripe"))
        assert source is not None
        source.enabled = False
        source_id = source.id
        assert bootstrap_seed_boards(session) == 0
    with session_factory() as session:
        source = session.get(Source, source_id)
        assert source is not None and source.enabled is False
        assert session.scalar(select(func.count()).select_from(Source)) == 9
        assert all(
            source.filter_config["level_terms"] for source in session.scalars(select(Source))
        )


def test_seed_boards_upgrade_only_unchanged_default_filters(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as session:
        bootstrap_seed_boards(session)
        openai = session.scalar(select(Source).where(Source.name == "ashby:openai"))
        notion = session.scalar(select(Source).where(Source.name == "ashby:notion"))
        assert openai is not None and notion is not None
        openai.filter_config = PREVIOUS_DEFAULT_FILTER
        notion.filter_config = {**DEFAULT_FILTER, "level_terms": ["custom graduate"]}
    with session_factory.begin() as session:
        assert bootstrap_seed_boards(session) == 0
    with session_factory() as session:
        openai = session.scalar(select(Source).where(Source.name == "ashby:openai"))
        notion = session.scalar(select(Source).where(Source.name == "ashby:notion"))
        assert openai is not None and notion is not None
        assert openai.filter_config == DEFAULT_FILTER
        assert notion.filter_config["level_terms"] == ["custom graduate"]


def test_seed_boards_upgrade_older_default_filter(session_factory: sessionmaker[Session]) -> None:
    with session_factory.begin() as session:
        bootstrap_seed_boards(session)
        stripe = session.scalar(select(Source).where(Source.name == "greenhouse:stripe"))
        assert stripe is not None
        stripe.filter_config = LEGACY_DEFAULT_FILTERS[1]
    with session_factory.begin() as session:
        bootstrap_seed_boards(session)
    with session_factory() as session:
        stripe = session.scalar(select(Source).where(Source.name == "greenhouse:stripe"))
        assert stripe is not None
        assert stripe.filter_config == DEFAULT_FILTER
