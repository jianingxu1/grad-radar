import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlparse


def normalize_apply_url(raw_url: str) -> str:
    candidate = raw_url.strip().lower()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("apply URL must be an absolute HTTP(S) URL")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if query.get("gh_jid"):
        return f"greenhouse-job-id:{query['gh_jid']}"
    if "greenhouse.io" in parsed.netloc and query.get("token"):
        return f"greenhouse-job-id:{query['token']}"
    if "microsoft.com" in parsed.netloc and query.get("pid"):
        return f"microsoft-job-id:{query['pid']}"
    path = parsed.path.rstrip("/")
    greenhouse = re.search(r"greenhouse\.io/(?:[^/]+/)?jobs/(\d+)", f"{parsed.netloc}{path}")
    if greenhouse:
        return f"greenhouse-job-id:{greenhouse.group(1)}"
    ashby = re.search(r"ashbyhq\.com/([^/]+)/([^/?#]+)", f"{parsed.netloc}{path}")
    if ashby:
        return f"ashby-job-id:{ashby.group(1)}:{ashby.group(2)}"
    host = parsed.netloc.removeprefix("www.")
    if host.endswith("greenhouse.io"):
        host = "boards.greenhouse.io"
    if "myworkdayjobs.com" in host:
        path = re.sub(r"^/[a-z]{2}(?:-[a-z]{2})?/", "/", path)
    path = re.sub(r"/(apply|application|detail)$", "", path).rstrip("/")
    if not path:
        path = ""
    return f"{parsed.scheme}://{host}{path}"


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
