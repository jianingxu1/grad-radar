"""Public ATS board readers. Fetching and filtering are separate steps."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import quote

import httpx

Platform = Literal["greenhouse", "ashby", "lever", "oracle"]
OracleConfig = dict[str, str]


@dataclass(frozen=True)
class BoardJob:
    posting_id: str
    title: str
    location: str
    apply_url: str
    description: str
    department: str
    employment_type: str
    listed_at: datetime | None
    country: str | None = None


def board_url(
    platform: Platform, board_name: str, platform_config: OracleConfig | None = None
) -> str:
    if platform == "oracle":
        config = validate_oracle_config(platform_config)
        return (
            f"https://{config['host']}/hcmUI/CandidateExperience/en/sites/{config['site_number']}"
        )
    board_name = quote(board_name, safe="-_.")
    if platform == "greenhouse":
        return f"https://job-boards.greenhouse.io/{board_name}"
    if platform == "ashby":
        return f"https://jobs.ashbyhq.com/{board_name}"
    return f"https://jobs.lever.co/{board_name}"


def fetch_board(
    client: httpx.Client,
    platform: Platform,
    board_name: str,
    platform_config: OracleConfig | None = None,
) -> list[BoardJob]:
    if platform == "oracle":
        config = validate_oracle_config(platform_config)
        return fetch_oracle(client, config)
    board_name = quote(board_name, safe="-_.")
    if platform == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_name}/jobs"
        return parse_greenhouse(_json(client.get(url, params={"content": "true"})))
    if platform == "ashby":
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board_name}"
        return parse_ashby(_json(client.get(url)))
    url = f"https://api.lever.co/v0/postings/{board_name}"
    jobs: list[BoardJob] = []
    for skip in range(0, 10000, 100):
        response = client.get(url, params={"mode": "json", "skip": skip, "limit": 100})
        batch = parse_lever(_json(response))
        jobs.extend(batch)
        if len(batch) < 100:
            return jobs
    raise ValueError("Lever board exceeds pagination limit")


def validate_oracle_config(config: OracleConfig | None) -> OracleConfig:
    if not isinstance(config, dict):
        raise ValueError("Oracle requires host and site_number")
    host = config.get("host", "").strip().lower()
    site_number = config.get("site_number", "").strip()
    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+oraclecloud\.com", host):
        raise ValueError("host must be an Oracle Cloud tenant hostname")
    if not re.fullmatch(r"CX(?:_\d+)?", site_number):
        raise ValueError("site_number must match CX or CX_<digits>")
    return {"host": host, "site_number": site_number}


def fetch_oracle(client: httpx.Client, config: OracleConfig) -> list[BoardJob]:
    endpoint = (
        f"https://{config['host']}/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions"
    )
    jobs: list[BoardJob] = []
    limit = 100
    offset = 0
    seen_ids: set[str] = set()
    while offset < 10000:
        finder = f"findReqs;siteNumber={config['site_number']},limit={limit},offset={offset}"
        response = client.get(
            endpoint,
            params={
                "onlyData": "true",
                "finder": finder,
                "expand": "requisitionList",
            },
        )
        response.raise_for_status()
        batch, total = parse_oracle(response.json(), config)
        batch_ids = {job.posting_id for job in batch}
        if len(batch_ids) != len(batch) or seen_ids.intersection(batch_ids):
            raise ValueError("Oracle pagination returned duplicate requisitions")
        jobs.extend(batch)
        seen_ids.update(batch_ids)
        if len(jobs) >= total:
            if len(jobs) != total:
                raise ValueError("Oracle returned more jobs than TotalJobsCount")
            return jobs
        if not batch:
            raise ValueError("Oracle pagination ended before TotalJobsCount")
        offset += len(batch)
    raise ValueError("Oracle board exceeds pagination limit")


def parse_oracle(payload: Any, config: OracleConfig) -> tuple[list[BoardJob], int]:
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        pages = payload["items"]
        if len(pages) != 1 or not isinstance(pages[0], dict):
            raise ValueError("Oracle response must contain one requisition search result")
        payload = pages[0]
    if not isinstance(payload, dict) or not isinstance(payload.get("requisitionList"), list):
        raise ValueError("Oracle response must contain requisitionList")
    total = payload.get("TotalJobsCount")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise ValueError("Oracle response must contain a valid TotalJobsCount")
    rows = payload["requisitionList"]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Oracle requisition must be an object")
    jobs: list[BoardJob] = []
    for row in rows:
        req_id = _required(row, "Id")
        job_id = str(req_id)
        if not re.fullmatch(r"\d+", job_id):
            raise ValueError("Oracle requisition Id must be numeric")
        location = str(row.get("PrimaryLocation") or "")
        country = row.get("PrimaryLocationCountry")
        listed = _date(row.get("PostedDate", row.get("PostingStartDate")))
        jobs.append(
            BoardJob(
                posting_id=job_id,
                title=_required_text(row, "Title"),
                location=location,
                apply_url=f"https://{config['host']}/hcmUI/CandidateExperience/en/sites/{config['site_number']}/job/{job_id}",
                description=str(row.get("ShortDescriptionStr", row.get("ShortDescription")) or ""),
                department="",
                employment_type="",
                listed_at=listed,
                country=str(country) if country else None,
            )
        )
    return jobs, total


def parse_greenhouse(payload: Any) -> list[BoardJob]:
    rows = _rows(payload, "jobs")
    jobs: list[BoardJob] = []
    for row in rows:
        if row.get("internal_job_id") is None:
            continue
        jobs.append(
            BoardJob(
                posting_id=str(_required(row, "id")),
                title=_required_text(row, "title"),
                location=_required_text(_required_dict(row, "location"), "name"),
                apply_url=_required_text(row, "absolute_url"),
                description=str(row.get("content") or ""),
                department=", ".join(
                    item.get("name", "")
                    for item in row.get("departments", [])
                    if isinstance(item, dict)
                ),
                employment_type="",
                listed_at=None,
            )
        )
    return jobs


def parse_ashby(payload: Any) -> list[BoardJob]:
    rows = _rows(payload, "jobs")
    jobs: list[BoardJob] = []
    for row in rows:
        if row.get("isListed") is not True:
            continue
        address = row.get("address") or {}
        postal = address.get("postalAddress") or {} if isinstance(address, dict) else {}
        jobs.append(
            BoardJob(
                posting_id=_required_text(row, "jobUrl").rstrip("/").split("/")[-1],
                title=_required_text(row, "title"),
                location=_required_text(row, "location"),
                apply_url=_required_text(row, "applyUrl"),
                description=str(row.get("descriptionPlain") or ""),
                department=str(row.get("department") or ""),
                employment_type=str(row.get("employmentType") or ""),
                listed_at=_date(row.get("publishedAt")),
                country=postal.get("addressCountry") if isinstance(postal, dict) else None,
            )
        )
    return jobs


def parse_lever(payload: Any) -> list[BoardJob]:
    if not isinstance(payload, list):
        raise ValueError("Lever response must be a list")
    jobs: list[BoardJob] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("Lever posting must be an object")
        categories = row.get("categories") or {}
        if not isinstance(categories, dict):
            raise ValueError("Lever categories must be an object")
        jobs.append(
            BoardJob(
                posting_id=_required_text(row, "id"),
                title=_required_text(row, "text"),
                location=_required_text(categories, "location"),
                apply_url=_required_text(row, "applyUrl"),
                description=str(row.get("descriptionPlain") or ""),
                department=str(categories.get("team") or categories.get("department") or ""),
                employment_type=str(categories.get("commitment") or ""),
                listed_at=None,
                country=row.get("country"),
            )
        )
    return jobs


def _json(response: httpx.Response) -> Any:
    response.raise_for_status()
    return response.json()


def _rows(payload: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        raise ValueError(f"board response must contain {key} list")
    if not all(isinstance(row, dict) for row in payload[key]):
        raise ValueError("board posting must be an object")
    return payload[key]


def _required(row: dict[str, Any], key: str) -> Any:
    value = row.get(key)
    if value is None:
        raise ValueError(f"missing {key}")
    return value


def _required_dict(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = _required(row, key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _required_text(row: dict[str, Any], key: str) -> str:
    value = _required(row, key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be nonempty text")
    return value


def _date(value: Any) -> datetime | None:
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError("publishedAt must be an ISO timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
