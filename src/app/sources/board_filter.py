"""Conservative, editable rules for public company-board jobs."""

import re
from typing import Any

from app.domain.job_posting_normalization import normalize_apply_url
from app.domain.location_eligibility import LocationEligibility, classify_us_location
from app.models.parsed_job_posting import ParsedJobPosting
from app.sources.ats import BoardJob

DEFAULT_FILTER: dict[str, list[str]] = {
    "role_terms": [
        "software engineer",
        "software developer",
        "software development engineer",
        "engineer i, software",
        "backend engineer",
        "frontend engineer",
        "front end engineer",
        "full stack engineer",
        "fullstack engineer",
        "forward deployed engineer",
        "ai platform engineer",
        "ai/ml engineer",
        "applied ai ncg",
    ],
    "level_terms": [
        "new grad",
        "new graduate",
        "university grad",
        "early career",
        "entry level",
        "emerging talent",
        "graduate",
        "university hire",
        "early careers",
        "campus",
        "grads",
        "ncg",
        "software engineer i",
    ],
    "exclude_terms": ["intern", "senior", "staff", "principal", "manager", "phd", "ph.d"],
}


def validate_filter(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict) or set(value) != set(DEFAULT_FILTER):
        raise ValueError("filter must contain role_terms, level_terms, and exclude_terms")
    result: dict[str, list[str]] = {}
    for key in DEFAULT_FILTER:
        terms = value[key]
        if not isinstance(terms, list) or not terms or len(terms) > 30:
            raise ValueError(f"{key} must contain 1 to 30 terms")
        if not all(isinstance(term, str) and 1 <= len(term.strip()) <= 80 for term in terms):
            raise ValueError(f"{key} contains an invalid term")
        result[key] = [term.strip().lower() for term in terms]
    return result


def matches_board_filter(job: BoardJob, config: dict[str, list[str]]) -> bool:
    title = job.title.lower()
    if not any(term in title for term in config["role_terms"]):
        return False
    level_in_title = any(
        re.search(rf"(?<!\w){re.escape(term)}(?!\w)", title) for term in config["level_terms"]
    )
    recent_graduate_description = (
        "graduate" in config["level_terms"]
        and re.search(r"\bgraduation expected between\b", job.description, re.IGNORECASE)
        is not None
    )
    if not (level_in_title or recent_graduate_description):
        return False
    if any(term in title for term in config["exclude_terms"]):
        return False
    employment = job.employment_type.lower().replace("-", "").replace(" ", "")
    if employment and employment not in {"fulltime", "fulltimeemployee"}:
        return False
    if job.country and job.country.upper() not in {"US", "USA", "UNITED STATES"}:
        return False
    return (
        classify_us_location(job.location) is LocationEligibility.ELIGIBLE
        or job.country is not None
        and job.country.upper() in {"US", "USA", "UNITED STATES"}
    )


def normalize_board_jobs(
    jobs: list[BoardJob], source_name: str, config: dict[str, list[str]], company_name: str
) -> list[ParsedJobPosting]:
    result: list[ParsedJobPosting] = []
    for position, job in enumerate(jobs):
        if not matches_board_filter(job, config):
            continue
        result.append(
            ParsedJobPosting(
                source_name=source_name,
                company_name=company_name,
                title=job.title,
                apply_url=job.apply_url,
                application_key=normalize_apply_url(job.apply_url),
                location=job.location,
                listed_at=job.listed_at,
                source_position=position,
            )
        )
    return result
