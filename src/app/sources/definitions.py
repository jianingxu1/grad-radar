from dataclasses import dataclass
from enum import StrEnum


class SourceName(StrEnum):
    SIMPLIFY = "simplify"
    SPEEDYAPPLY = "speedyapply"


@dataclass(frozen=True)
class SourceDefinition:
    name: SourceName
    repository: str
    branch: str
    file_path: str
    parser: SourceName
    priority: int

    @property
    def url(self) -> str:
        return f"https://github.com/{self.repository}"


SOURCES = (
    SourceDefinition(
        SourceName.SIMPLIFY,
        "SimplifyJobs/New-Grad-Positions",
        "dev",
        "README.md",
        SourceName.SIMPLIFY,
        1,
    ),
    SourceDefinition(
        SourceName.SPEEDYAPPLY,
        "speedyapply/2027-SWE-College-Jobs",
        "main",
        "NEW_GRAD_USA.md",
        SourceName.SPEEDYAPPLY,
        2,
    ),
)
