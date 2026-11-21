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
    url: str


SOURCES = (
    SourceDefinition(
        name=SourceName.SIMPLIFY,
        repository="SimplifyJobs/New-Grad-Positions",
        branch="dev",
        file_path="README.md",
        parser=SourceName.SIMPLIFY,
        priority=1,
        url="https://github.com/SimplifyJobs/New-Grad-Positions#-software-engineering-new-grad-roles",
    ),
    SourceDefinition(
        name=SourceName.SPEEDYAPPLY,
        repository="speedyapply/2027-SWE-College-Jobs",
        branch="main",
        file_path="NEW_GRAD_USA.md",
        parser=SourceName.SPEEDYAPPLY,
        priority=2,
        url="https://github.com/speedyapply/2027-SWE-College-Jobs/blob/main/NEW_GRAD_USA.md",
    ),
)
