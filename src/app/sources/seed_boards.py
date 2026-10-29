"""Verified public boards to include on every GradRadar installation."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Source
from app.sources.ats import Platform, board_url
from app.sources.board_filter import DEFAULT_FILTER


@dataclass(frozen=True)
class SeedBoard:
    platform: Platform
    board_name: str
    company_name: str

    @property
    def name(self) -> str:
        return f"{self.platform}:{self.board_name.casefold()}"


SEED_BOARDS = (
    SeedBoard("greenhouse", "stripe", "Stripe"),
    SeedBoard("greenhouse", "databricks", "Databricks"),
    SeedBoard("greenhouse", "coinbase", "Coinbase"),
    SeedBoard("ashby", "openai", "OpenAI"),
    SeedBoard("ashby", "notion", "Notion"),
    SeedBoard("ashby", "ramp", "Ramp"),
    SeedBoard("lever", "palantir", "Palantir"),
    SeedBoard("lever", "shieldai", "Shield AI"),
    SeedBoard("lever", "spotify", "Spotify"),
)


def bootstrap_seed_boards(session: Session) -> int:
    existing = set(session.scalars(select(Source.name)).all())
    created = 0
    for board in SEED_BOARDS:
        if board.name in existing:
            continue
        session.add(
            Source(
                name=board.name,
                url=board_url(board.platform, board.board_name),
                platform=board.platform,
                board_name=board.board_name,
                company_name=board.company_name,
                filter_config=DEFAULT_FILTER,
                priority=100,
            )
        )
        created += 1
    return created
