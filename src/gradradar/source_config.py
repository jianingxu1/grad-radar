from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    repository: str
    branch: str
    file_path: str
    parser: str
    priority: int

    @property
    def url(self) -> str:
        return f"https://github.com/{self.repository}"


SOURCES = (
    SourceDefinition(
        "simplify", "SimplifyJobs/New-Grad-Positions", "dev", "README.md", "simplify", 1
    ),
    SourceDefinition(
        "speedyapply",
        "speedyapply/2027-SWE-College-Jobs",
        "main",
        "NEW_GRAD_USA.md",
        "speedyapply",
        2,
    ),
)
