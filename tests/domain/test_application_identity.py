from datetime import UTC, datetime

import pytest

from gradradar.domain.application_identity import normalize_apply_url, parse_tracker_age


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (" https://www.example.com/jobs/1/?utm=x#top ", "https://example.com/jobs/1"),
        ("https://boards.greenhouse.io/acme/jobs/123?gh_jid=456", "greenhouse-job-id:456"),
        ("https://jobs.ashbyhq.com/acme/abc", "ashby-job:acme:abc"),
    ],
)
def test_normalize_apply_url(url: str, expected: str) -> None:
    assert normalize_apply_url(url) == expected


def test_normalize_apply_url_rejects_relative_urls() -> None:
    with pytest.raises(ValueError):
        normalize_apply_url("/jobs/1")


def test_parse_tracker_age() -> None:
    reference = datetime(2026, 1, 2, tzinfo=UTC)
    assert parse_tracker_age("3d", reference) == datetime(2025, 12, 30, tzinfo=UTC)
    assert parse_tracker_age("bad", reference) is None
