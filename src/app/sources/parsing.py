from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from bs4 import BeautifulSoup

from app.domain.job_posting_normalization import normalize_apply_url, parse_tracker_age
from app.domain.location_eligibility import LocationEligibility, classify_us_location
from app.models.parsed_job_posting import ParsedJobPosting
from app.sources.definitions import SourceName


@dataclass
class ParseResult:
    postings: list[ParsedJobPosting]
    parsed: int = 0
    ineligible: int = 0
    unknown: int = 0
    malformed: int = 0


class SourceParser(Protocol):
    def parse(self, text: str, revision_at: datetime) -> ParseResult: ...


class SpeedyApplyParser:
    def parse(self, text: str, revision_at: datetime) -> ParseResult:
        return _parse_speedyapply(text, revision_at)


class SimplifyParser:
    def parse(self, text: str, revision_at: datetime) -> ParseResult:
        return _parse_simplify(text, revision_at)


PARSERS: dict[SourceName, SourceParser] = {
    SourceName.SIMPLIFY: SimplifyParser(),
    SourceName.SPEEDYAPPLY: SpeedyApplyParser(),
}


def get_parser(name: SourceName) -> SourceParser:
    try:
        return PARSERS[name]
    except KeyError as error:
        raise ValueError(f"unsupported source parser: {name}") from error


def _parse_speedyapply(text: str, revision_at: datetime) -> ParseResult:
    heading = "2027 USA SWE New Graduate Positions"
    result = ParseResult([])
    active = False
    in_target_section = False
    found_target_section = False
    headers: dict[str, int] | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            in_target_section = heading in line
            found_target_section = found_target_section or in_target_section
            active = False
            headers = None
            continue
        if (
            in_target_section
            and line.strip().lower().startswith("###")
            and any(x in line for x in ("FAANG+", "Quant", "Other"))
        ):
            active = True
            headers = None
        if not active or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if headers is None:
            headers = {header.lower(): index for index, header in enumerate(cells)}
            required = {"company", "position", "location", "posting", "age"}
            if not required <= headers.keys():
                raise ValueError("missing SpeedyApply table columns")
            continue
        if len(cells) < len(headers):
            result.malformed += 1
            continue
        result.parsed += 1
        posting_cell = cells[headers["posting"]]
        _append(
            result,
            SourceName.SPEEDYAPPLY,
            cells[headers["company"]],
            cells[headers["position"]],
            cells[headers["location"]],
            cells[headers["age"]],
            revision_at,
            _first_url(posting_cell),
        )
    if not found_target_section:
        raise ValueError("missing SpeedyApply new-grad heading")
    return result


def _parse_simplify(text: str, revision_at: datetime) -> ParseResult:
    marker = "## 💻 Software Engineering New Grad Roles"
    if marker not in text:
        raise ValueError("missing Simplify SWE heading")
    section = (
        text.split(marker, 1)[1].split("Inactive roles", 1)[0].split("## Product Management", 1)[0]
    )
    soup = BeautifulSoup(section, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError("missing Simplify roles table")
    result, previous_company = ParseResult([]), None
    for row in table.find_all("tr")[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 5:
            continue
        values = [cell.get_text("\n", strip=True) for cell in cells]
        company = values[0]
        if company.startswith("↳"):
            if previous_company is None:
                result.malformed += 1
                continue
            company = previous_company
        else:
            previous_company = company
        anchor = next((a for a in cells[3].find_all("a") if a.find("img", alt="Apply")), None)
        if anchor is None or not anchor.get("href"):
            continue
        result.parsed += 1
        _append(
            result,
            SourceName.SIMPLIFY,
            company,
            values[1],
            values[2],
            values[4],
            revision_at,
            str(anchor["href"]),
        )
    return result


def _append(
    result: ParseResult,
    source: SourceName,
    company: str,
    title: str,
    location: str,
    age: str,
    revision_at: datetime,
    url: str | None = None,
) -> None:
    url = url or _first_url(title)
    if url is None:
        result.malformed += 1
        return
    eligibility = classify_us_location(location)
    if eligibility is LocationEligibility.INELIGIBLE:
        result.ineligible += 1
        return
    if eligibility is LocationEligibility.UNKNOWN:
        result.unknown += 1
        return
    try:
        result.postings.append(
            ParsedJobPosting(
                source_name=source,
                company_name=company,
                title=title,
                apply_url=url,
                application_key=normalize_apply_url(url),
                location=location,
                listed_at=parse_tracker_age(age, revision_at),
            )
        )
    except ValueError:
        result.malformed += 1


def _first_url(value: str) -> str | None:
    import re

    match = re.search(r'https?://[^\s)"<>\]]+', value)
    return match.group(0) if match else None
