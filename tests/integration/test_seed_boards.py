from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Source
from app.sources.seed_boards import bootstrap_seed_boards


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
