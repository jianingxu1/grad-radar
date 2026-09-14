import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlparse


def normalize_apply_url(raw_url: str) -> str:
    candidate = raw_url.strip().lower()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("apply URL must be an absolute HTTP(S) URL")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    path = parsed.path.rstrip("/")

    greenhouse_key = _greenhouse_key(parsed.netloc, path, query)
    if greenhouse_key is not None:
        return greenhouse_key

    ashby_key = _ashby_key(parsed.netloc, path)
    if ashby_key is not None:
        return ashby_key

    if "microsoft.com" in parsed.netloc and query.get("pid"):
        return f"microsoft-job-id:{query['pid']}"

    host = parsed.netloc.removeprefix("www.")
    if host.endswith("greenhouse.io"):
        host = "boards.greenhouse.io"
    if "myworkdayjobs.com" in host:
        path = re.sub(r"^/[a-z]{2}(?:-[a-z]{2})?/", "/", path)
    path = re.sub(r"/(apply|application|detail)$", "", path).rstrip("/")
    if not path:
        path = ""
    return f"{parsed.scheme}://{host}{path}"


def _greenhouse_key(host: str, path: str, query: dict[str, str]) -> str | None:
    if query.get("gh_jid"):
        return f"greenhouse-job-id:{query['gh_jid']}"
    if "greenhouse.io" in host and query.get("token"):
        return f"greenhouse-job-id:{query['token']}"
    match = re.search(r"greenhouse\.io/(?:[^/]+/)?jobs/(\d+)", f"{host}{path}")
    if match:
        return f"greenhouse-job-id:{match.group(1)}"
    return None


def _ashby_key(host: str, path: str) -> str | None:
    match = re.search(r"ashbyhq\.com/([^/]+)/([^/?#]+)", f"{host}{path}")
    if match:
        return f"ashby-job-id:{match.group(1)}:{match.group(2)}"
    return None


def parse_tracker_age(age: str, reference_time: datetime) -> datetime | None:
    match = re.fullmatch(r"\s*(\d+)\s*(h|d|mo)\s*", age.lower())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    reference = reference_time.astimezone(UTC)
    duration = {
        "h": timedelta(hours=amount),
        "d": timedelta(days=amount),
        "mo": timedelta(days=30 * amount),
    }[unit]
    return reference - duration
