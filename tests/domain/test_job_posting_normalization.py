from datetime import UTC, datetime

import pytest

from app.domain.job_posting_normalization import normalize_apply_url, parse_tracker_age


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://jobs.ashbyhq.com/netic/d9bcb6a2-0e54-4cb3-baec-43f2d74db18f?source=LI",
            "ashby-job-id:netic:d9bcb6a2-0e54-4cb3-baec-43f2d74db18f",
        ),
        (
            "https://jobs.ashbyhq.com/pylon-labs/38814ce7-217b-40f2-9ba5-8a7733a5691d/application?utm_source=Simplify",
            "ashby-job-id:pylon-labs:38814ce7-217b-40f2-9ba5-8a7733a5691d",
        ),
        (
            "https://job-boards.eu.greenhouse.io/imc/jobs/4577504101?gh_src=aee47bb2teu",
            "greenhouse-job-id:4577504101",
        ),
        (
            "https://job-boards.greenhouse.io/embed/job_app?for=jumptrading&gh_src=Simplify&token=8000835&utm_source=Simplify",
            "greenhouse-job-id:8000835",
        ),
        (
            "https://app.careerpuck.com/job-board/lyft/job/8678744002?gh_jid=8678744002",
            "greenhouse-job-id:8678744002",
        ),
        (
            "https://www.google.com/about/careers/applications/jobs/results/131345817104458438-software-engineer-ii-ai-scheduling?q=%22Software%20Engineer%22&hl=en&client=safari&target_level=EARLY",
            "https://google.com/about/careers/applications/jobs/results/131345817104458438-software-engineer-ii-ai-scheduling",
        ),
        (
            "https://www.amazon.jobs/en/jobs/3144341/software-development-engineer-amazon-leo-us",
            "https://amazon.jobs/en/jobs/3144341/software-development-engineer-amazon-leo-us",
        ),
        (
            "https://jobs.intuit.com/job/-/-/27595/87369448720?cid=pjob_li_click_us_swe-other-fy27_cn_text_job_int-tm&iis=pjob&iisn=li&p_sid=o1ZxvUb&p_uid=z60CdU1XHz",
            "https://jobs.intuit.com/job/-/-/27595/87369448720",
        ),
        (
            "https://jobs.lever.co/weride/5cde0d09-ba2d-408d-947e-4a42028cd4f7/apply?lever-source=Simplify",
            "https://jobs.lever.co/weride/5cde0d09-ba2d-408d-947e-4a42028cd4f7",
        ),
        (
            "https://jobs.bytedance.com/en/position/7667901772678302005/detail",
            "https://jobs.bytedance.com/en/position/7667901772678302005",
        ),
    ],
)
def test_normalize_apply_url(url: str, expected: str) -> None:
    assert normalize_apply_url(url) == expected


@pytest.mark.parametrize("url", ["", "/jobs/1", "ftp://example.com/job", "example.com/job"])
def test_normalize_apply_url_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_apply_url(url)


def test_parse_tracker_age() -> None:
    reference = datetime(2026, 1, 2, tzinfo=UTC)
    assert parse_tracker_age("3d", reference) == datetime(2025, 12, 30, tzinfo=UTC)
    assert parse_tracker_age("bad", reference) is None
