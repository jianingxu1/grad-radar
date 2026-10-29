from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.sources.ats import (
    board_url,
    fetch_board,
    parse_ashby,
    parse_greenhouse,
    parse_lever,
    parse_oracle,
)


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


@respx.mock
def test_ashby_board_name_with_spaces_is_encoded() -> None:
    endpoint = respx.get(
        "https://api.ashbyhq.com/posting-api/job-board/Superhuman%20Platform%20Inc"
    ).mock(return_value=httpx.Response(200, json={"jobs": []}))
    with httpx.Client() as client:
        assert fetch_board(client, "ashby", "Superhuman Platform Inc") == []
    assert endpoint.called
    assert board_url("ashby", "Superhuman Platform Inc") == (
        "https://jobs.ashbyhq.com/Superhuman%20Platform%20Inc"
    )


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


def test_oracle_parser_maps_optional_fields_and_rejects_bad_payloads() -> None:
    config = {"host": "example.fa.oraclecloud.com", "site_number": "CX_1"}
    jobs, total = parse_oracle(
        {
            "TotalJobsCount": 1,
            "requisitionList": [
                {
                    "Id": 123,
                    "Title": "Software Engineer New Grad",
                    "PrimaryLocation": "Seattle, WA",
                    "PrimaryLocationCountry": "United States",
                    "PostedDate": "2026-10-28T00:00:00Z",
                    "ShortDescriptionStr": "Build software",
                }
            ],
        },
        config,
    )
    assert total == 1
    assert jobs[0].posting_id == "123"
    assert jobs[0].apply_url.endswith("/sites/CX_1/job/123")
    assert jobs[0].listed_at == datetime(2026, 10, 28, tzinfo=UTC)
    assert jobs[0].country == "United States"
    date_only, _ = parse_oracle(
        {
            "TotalJobsCount": 1,
            "requisitionList": [{"Id": 7, "Title": "Engineer", "PostedDate": "2026-10-28"}],
        },
        config,
    )
    assert date_only[0].listed_at == datetime(2026, 10, 28, tzinfo=UTC)
    optional, _ = parse_oracle(
        {
            "TotalJobsCount": 1,
            "requisitionList": [
                {
                    "Id": 2,
                    "Title": "Engineer",
                }
            ],
        },
        config,
    )
    assert optional[0].description == "" and optional[0].listed_at is None
    for payload in (
        {},
        {"TotalJobsCount": -1, "requisitionList": []},
        {"TotalJobsCount": 1, "requisitionList": [None]},
        {
            "TotalJobsCount": 1,
            "requisitionList": [{"Id": 1, "Title": "Role", "PostingStartDate": "bad"}],
        },
    ):
        with pytest.raises(ValueError):
            parse_oracle(payload, config)


@respx.mock
def test_oracle_fetches_all_pages_with_finder_and_configured_site() -> None:
    host = "example.fa.oraclecloud.com"
    url = f"https://{host}/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions"
    calls = []

    def page(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params)
        finder = request.url.params["finder"]
        offset = int(finder.rsplit("offset=", 1)[1])
        rows = [
            {"Id": index + 1, "Title": "Role"} for index in range(offset, min(offset + 100, 101))
        ]
        return httpx.Response(200, json={"TotalJobsCount": 101, "requisitionList": rows})

    respx.get(url).mock(side_effect=page)
    with httpx.Client() as client:
        jobs = fetch_board(client, "oracle", "uber", {"host": host, "site_number": "CX_1"})
    assert len(jobs) == 101
    assert len(calls) == 2
    assert calls[0]["finder"] == "findReqs;siteNumber=CX_1,limit=100,offset=0"
    assert calls[0]["onlyData"] == "true"
    assert calls[1]["finder"].endswith("offset=100")


@respx.mock
def test_oracle_http_error_and_invalid_config_fail() -> None:
    host = "example.fa.oraclecloud.com"
    url = f"https://{host}/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions"
    respx.get(url).mock(return_value=httpx.Response(503))
    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        fetch_board(client, "oracle", "uber", {"host": host, "site_number": "CX"})
    with httpx.Client() as client, pytest.raises(ValueError):
        fetch_board(client, "oracle", "uber", {"host": "evil.com", "site_number": "CX_1"})


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
