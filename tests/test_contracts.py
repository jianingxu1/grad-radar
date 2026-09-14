from datetime import UTC, datetime

from gradradar.contracts import ParsedJobPosting


def test_parsed_posting_accepts_shared_contract() -> None:
    posting = ParsedJobPosting(
        source_name="simplify",
        company_name="Acme",
        title="SWE",
        apply_url="https://example.com/job",
        application_key="https://example.com/job",
        location="USA",
        listed_at=datetime.now(UTC),
    )
    assert posting.source_name == "simplify"
