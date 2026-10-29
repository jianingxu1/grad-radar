from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPostingSource, Source
from app.sources.bootstrap import bootstrap_sources


def test_existing_github_sources_keep_defaults(session_factory: sessionmaker[Session]) -> None:
    with session_factory.begin() as session:
        assert bootstrap_sources(session) == 2
    with session_factory() as session:
        sources = session.scalars(select(Source).order_by(Source.name)).all()
        observed = [
            (source.name, source.platform, source.enabled, source.priority) for source in sources
        ]
        assert observed == [
            ("simplify", "github", True, 1),
            ("speedyapply", "github", True, 2),
        ]
        assert all(source.filter_config == {} for source in sources)
        assert "active" in JobPostingSource.__table__.columns
