from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import JobPostingSource, Source
from app.sources.bootstrap import bootstrap_sources

GITHUB_SOURCE_URLS = {
    "simplify": (
        "https://github.com/SimplifyJobs/New-Grad-Positions#-software-engineering-new-grad-roles"
    ),
    "speedyapply": "https://github.com/speedyapply/2027-SWE-College-Jobs/blob/main/NEW_GRAD_USA.md",
}


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
        assert {source.name: source.url for source in sources} == GITHUB_SOURCE_URLS
        assert "active" in JobPostingSource.__table__.columns


def test_bootstrap_refreshes_github_urls_without_resetting_sources(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as session:
        bootstrap_sources(session)
        sources = session.scalars(select(Source).order_by(Source.name)).all()
        original_ids = {source.name: source.id for source in sources}
        for source in sources:
            source.url = "https://github.com/old/repository"
            source.enabled = False
            source.priority = 10
        board = Source(
            name="greenhouse:figma",
            platform="greenhouse",
            board_name="figma",
            url="https://job-boards.greenhouse.io/figma",
            priority=20,
        )
        session.add(board)

    with session_factory.begin() as session:
        assert bootstrap_sources(session) == 0

    with session_factory() as session:
        sources = session.scalars(select(Source).where(Source.platform == "github")).all()
        assert {source.name: source.url for source in sources} == GITHUB_SOURCE_URLS
        assert {source.name: source.id for source in sources} == original_ids
        assert all(not source.enabled and source.priority == 10 for source in sources)
        stored_board = session.get(Source, board.id)
        assert stored_board is not None
        assert stored_board.url == "https://job-boards.greenhouse.io/figma"
