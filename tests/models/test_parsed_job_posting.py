from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.models.parsed_job_posting import ParsedJobPosting
from app.sources.definitions import SourceName


def test_parsed_posting_accepts_shared_contract() -> None:
    posting = ParsedJobPosting(
        source_name=SourceName.SIMPLIFY,
        company_name="Acme",
        title="SWE",
        apply_url="https://example.com/job",
        application_key="https://example.com/job",
        location="USA",
        listed_at=datetime.now(UTC),
        source_position=0,
    )
    assert posting.source_name == SourceName.SIMPLIFY


def test_parsed_posting_rejects_non_utc_listing_time_and_preserves_url() -> None:
    with pytest.raises(ValueError):
        ParsedJobPosting(
            source_name=SourceName.SIMPLIFY,
            company_name="Acme",
            title="SWE",
            apply_url="https://EXAMPLE.com/job",
            application_key="key",
            location="USA",
            listed_at=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=1))),
            source_position=0,
        )
