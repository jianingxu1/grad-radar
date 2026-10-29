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

PREVIOUS_DEFAULT_FILTER = {
    "role_terms": DEFAULT_FILTER["role_terms"][:9],
    "level_terms": DEFAULT_FILTER["level_terms"][:7],
    "exclude_terms": DEFAULT_FILTER["exclude_terms"],
}
LEGACY_DEFAULT_FILTERS = (
    PREVIOUS_DEFAULT_FILTER,
    {**PREVIOUS_DEFAULT_FILTER, "level_terms": PREVIOUS_DEFAULT_FILTER["level_terms"][:-1]},
)


def bootstrap_seed_boards(session: Session) -> int:
    existing = {source.name: source for source in session.scalars(select(Source)).all()}
    created = 0
    for board in SEED_BOARDS:
        if board.name in existing:
            source = existing[board.name]
            if source.filter_config in LEGACY_DEFAULT_FILTERS:
                source.filter_config = DEFAULT_FILTER
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
