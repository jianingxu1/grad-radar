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
    platform_config: dict[str, str] | None = None

    @property
    def name(self) -> str:
        return f"{self.platform}:{self.board_name.casefold()}"


SEED_BOARDS = (
    SeedBoard(
        "oracle", "uber", "Uber", {"host": "iaziqy.fa.ocs.oraclecloud.com", "site_number": "CX_1"}
    ),
    SeedBoard("greenhouse", "stripe", "Stripe"),
    SeedBoard("greenhouse", "databricks", "Databricks"),
    SeedBoard("greenhouse", "coinbase", "Coinbase"),
    SeedBoard("greenhouse", "anthropic", "Anthropic"),
    SeedBoard("greenhouse", "scaleai", "Scale AI"),
    SeedBoard("greenhouse", "gleanwork", "Glean"),
    SeedBoard("greenhouse", "figma", "Figma"),
    SeedBoard("greenhouse", "Discord", "Discord"),
    SeedBoard("greenhouse", "doordashusa", "DoorDash"),
    SeedBoard("greenhouse", "imc", "IMC"),
    SeedBoard("greenhouse", "hudsonrivertrading", "Hudson River Trading"),
    SeedBoard("greenhouse", "domino-data-lab", "Domino Data Lab"),
    SeedBoard("greenhouse", "optiver", "Optiver"),
    SeedBoard("greenhouse", "lyft", "Lyft"),
    SeedBoard("greenhouse", "samsara", "Samsara"),
    SeedBoard("greenhouse", "roblox", "Roblox"),
    SeedBoard("greenhouse", "akunacapital", "Akuna Capital"),
    SeedBoard("greenhouse", "twitch", "Twitch"),
    SeedBoard("greenhouse", "kikoff", "Kikoff"),
    SeedBoard("greenhouse", "jumptrading", "Jump Trading"),
    SeedBoard("greenhouse", "freeformfuturecorp", "Freeform Future"),
    SeedBoard("greenhouse", "idmeuniversityrecruiting", "ID.me"),
    SeedBoard("greenhouse", "instabase", "Instabase"),
    SeedBoard("greenhouse", "singlestore", "SingleStore"),
    SeedBoard("greenhouse", "2kearlycareers", "2K"),
    SeedBoard("greenhouse", "togetherai", "Together AI"),
    SeedBoard("greenhouse", "ziprecruiter", "ZipRecruiter"),
    SeedBoard("greenhouse", "affirm", "Affirm"),
    SeedBoard("greenhouse", "asteraearlycareer2027", "Astera"),
    SeedBoard("greenhouse", "nuro", "Nuro"),
    SeedBoard("greenhouse", "c3ai", "C3.ai"),
    SeedBoard("greenhouse", "ixl", "IXL"),
    SeedBoard("greenhouse", "otterai", "Otter.ai"),
    SeedBoard("greenhouse", "sambanova", "SambaNova"),
    SeedBoard("greenhouse", "pinterest", "Pinterest"),
    SeedBoard("ashby", "openai", "OpenAI"),
    SeedBoard("ashby", "notion", "Notion"),
    SeedBoard("ashby", "ramp", "Ramp"),
    SeedBoard("ashby", "linear", "Linear"),
    SeedBoard("ashby", "replit", "Replit"),
    SeedBoard("ashby", "perplexity", "Perplexity"),
    SeedBoard("ashby", "plaid", "Plaid"),
    SeedBoard("ashby", "cohere", "Cohere"),
    SeedBoard("ashby", "vanta", "Vanta"),
    SeedBoard("ashby", "zip", "Zip"),
    SeedBoard("ashby", "supabase", "Supabase"),
    SeedBoard("ashby", "huggingface", "Hugging Face"),
    SeedBoard("ashby", "applied", "Applied"),
    SeedBoard("ashby", "netic", "Netic"),
    SeedBoard("ashby", "pylon-labs", "Pylon Labs"),
    SeedBoard("ashby", "sierra", "Sierra"),
    SeedBoard("ashby", "whatnot", "Whatnot"),
    SeedBoard("ashby", "nooks", "Nooks"),
    SeedBoard("ashby", "Lightfield", "Lightfield"),
    SeedBoard("ashby", "zettabyte-space", "Zettabyte Space"),
    SeedBoard("ashby", "Valon", "Valon"),
    SeedBoard("ashby", "arch.co", "Arch"),
    SeedBoard("ashby", "siftstack", "Siftstack"),
    SeedBoard("ashby", "elevenlabs", "ElevenLabs"),
    SeedBoard("ashby", "greenboard", "Greenboard"),
    SeedBoard("ashby", "commure", "Commure"),
    SeedBoard("ashby", "retell-ai", "Retell AI"),
    SeedBoard("ashby", "Superhuman Platform Inc", "Superhuman"),
    SeedBoard("ashby", "whoop", "WHOOP"),
    SeedBoard("ashby", "Crusoe", "Crusoe"),
    SeedBoard("ashby", "radiant-industries", "Radiant Industries"),
    SeedBoard("ashby", "voleon", "Voleon"),
    SeedBoard("ashby", "brainco", "BrainCo"),
    SeedBoard("ashby", "amplitude", "Amplitude"),
    SeedBoard("ashby", "hyphenate", "Hyphenate"),
    SeedBoard("ashby", "chalk", "Chalk"),
    SeedBoard("ashby", "spruceid", "SpruceID"),
    SeedBoard("ashby", "harvey", "Harvey"),
    SeedBoard("ashby", "parasail", "Parasail"),
    SeedBoard("ashby", "claylabs", "Clay"),
    SeedBoard("lever", "palantir", "Palantir"),
    SeedBoard("lever", "shieldai", "Shield AI"),
    SeedBoard("lever", "spotify", "Spotify"),
    SeedBoard("lever", "weride", "WeRide"),
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
                url=board_url(board.platform, board.board_name, board.platform_config),
                platform=board.platform,
                board_name=board.board_name,
                company_name=board.company_name,
                filter_config=DEFAULT_FILTER,
                platform_config=board.platform_config,
                priority=100,
            )
        )
        created += 1
    return created
