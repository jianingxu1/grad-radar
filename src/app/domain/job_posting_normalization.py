import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, unquote, urlencode, urlparse

TRACKING_QUERY_PARAMETERS = frozenset(
    {
        "cid",
        "client",
        "gh_src",
        "hl",
        "iis",
        "iisn",
        "lever-source",
        "p_sid",
        "p_uid",
        "q",
        "ref",
        "referrer",
        "source",
        "src",
        "target_level",
    }
)


def normalize_apply_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    parsed = urlparse(candidate)
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()
    if scheme not in {"http", "https"} or not host:
        raise ValueError("apply URL must be an absolute HTTP(S) URL")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    path = parsed.path.rstrip("/")

    greenhouse_key = _greenhouse_key(host, path, query)
    if greenhouse_key is not None:
        return greenhouse_key

    ashby_key = _ashby_key(host, path)
    if ashby_key is not None:
        return ashby_key

    microsoft_key = _microsoft_key(host, query)
    if microsoft_key is not None:
        return microsoft_key

    host = host.removeprefix("www.")
    if host.endswith("greenhouse.io"):
        host = "boards.greenhouse.io"
    if "myworkdayjobs.com" in host:
        path = re.sub(r"^/[a-z]{2}(?:-[a-z]{2})?/", "/", path)
    path = re.sub(r"/(apply|application|detail)$", "", path).rstrip("/")
    if not path:
        path = ""
    normalized_query = _normalize_query(parsed.query)
    query_suffix = f"?{normalized_query}" if normalized_query else ""
    return f"{scheme}://{host}{path}{query_suffix}"


def _normalize_query(query: str) -> str:
    retained = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=True)
        if not (key.lower().startswith("utm_") or key.lower() in TRACKING_QUERY_PARAMETERS)
    ]
    return urlencode(sorted(retained))


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
        board = unquote(match.group(1)).casefold()
        job_id = unquote(match.group(2))
        return f"ashby-job-id:{board}:{job_id}"
    return None


def _microsoft_key(host: str, query: dict[str, str]) -> str | None:
    if "microsoft.com" in host and query.get("pid"):
        return f"microsoft-job-id:{query['pid']}"
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
