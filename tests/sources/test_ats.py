from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.sources.ats import fetch_board, parse_ashby, parse_greenhouse, parse_lever


def test_greenhouse_parse_skips_prospect_and_does_not_use_update_as_listing_date() -> None:
    payload = {
        "jobs": [
            {
                "id": 123,
                "internal_job_id": 456,
                "title": "Software Engineer, New Grad",
                "location": {"name": "San Francisco, CA"},
                "absolute_url": "https://job-boards.greenhouse.io/stripe/jobs/123",
                "updated_at": "2026-10-28T00:00:00Z",
                "content": "Graduate software role",
                "departments": [{"name": "Engineering"}],
            },
            {"id": 124, "internal_job_id": None},
        ]
    }
    jobs = parse_greenhouse(payload)
    assert len(jobs) == 1
    assert jobs[0].posting_id == "123"
    assert jobs[0].listed_at is None
    assert jobs[0].department == "Engineering"


def test_ashby_parse_skips_unlisted_and_uses_published_date() -> None:
    payload = {
        "apiVersion": "1",
        "jobs": [
            {
                "title": "Software Engineer, New Grad",
                "location": "San Francisco",
                "jobUrl": "https://jobs.ashbyhq.com/openai/abc",
                "applyUrl": "https://jobs.ashbyhq.com/openai/abc/application",
                "isListed": True,
                "publishedAt": "2026-10-28T12:00:00Z",
                "employmentType": "FullTime",
                "address": {"postalAddress": {"addressCountry": "USA"}},
            },
            {"isListed": False},
        ],
    }
    jobs = parse_ashby(payload)
    assert len(jobs) == 1
    assert jobs[0].country == "USA"
    assert jobs[0].listed_at == datetime(2026, 10, 28, 12, tzinfo=UTC)


def test_lever_parse_and_empty_board() -> None:
    assert parse_lever([]) == []
    jobs = parse_lever(
        [
            {
                "id": "abc",
                "text": "Software Engineer, New Grad",
                "categories": {"location": "New York, NY", "commitment": "Full-time"},
                "applyUrl": "https://jobs.lever.co/palantir/abc/apply",
                "country": "US",
            }
        ]
    )
    assert jobs[0].posting_id == "abc"
    assert jobs[0].listed_at is None


@respx.mock
def test_fetch_board_uses_fixed_hosts_and_paginates_lever() -> None:
    respx.get("https://boards-api.greenhouse.io/v1/boards/stripe/jobs").mock(
        return_value=httpx.Response(200, json={"jobs": []})
    )
    respx.get("https://api.ashbyhq.com/posting-api/job-board/openai").mock(
        return_value=httpx.Response(200, json={"jobs": []})
    )
    lever = respx.get("https://api.lever.co/v0/postings/palantir").mock(
        return_value=httpx.Response(200, json=[])
    )
    with httpx.Client() as client:
        assert fetch_board(client, "greenhouse", "stripe") == []
        assert fetch_board(client, "ashby", "openai") == []
        assert fetch_board(client, "lever", "palantir") == []
    assert lever.call_count == 1


@pytest.mark.parametrize(
    "parser,payload",
    [(parse_greenhouse, {}), (parse_ashby, {"jobs": None}), (parse_lever, {})],
)
def test_malformed_boards_fail(parser, payload) -> None:
    with pytest.raises(ValueError):
        parser(payload)
