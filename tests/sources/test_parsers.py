from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.sources.definitions import SourceName
from app.sources.parsing import SimplifyParser, SpeedyApplyParser, get_parser


def test_speedyapply_parser_maps_headers_and_posting_link() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "speedyapply_new_grad.md"
    result = SpeedyApplyParser().parse(fixture.read_text(), datetime(2026, 1, 3, tzinfo=UTC))

    assert [posting.company_name for posting in result.postings] == [
        "Amazon",
        "Jane Street",
        "Replit",
    ]
    assert [posting.source_name for posting in result.postings] == [SourceName.SPEEDYAPPLY] * 3


def test_simplify_parser_selects_apply_link_and_us_row() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "simplify_new_grad.md"
    result = SimplifyParser().parse(fixture.read_text(), datetime(2026, 1, 3, tzinfo=UTC))

    assert [posting.company_name for posting in result.postings] == ["Autostore", "Klaviyo"]
    assert result.postings[0].apply_url.startswith("https://autostore.wd3.myworkdayjobs.com")
    assert result.postings[1].apply_url.startswith("https://job-boards.greenhouse.io")
    assert result.ineligible == 1


def test_parser_registry_resolves_known_sources() -> None:
    assert isinstance(get_parser(SourceName.SIMPLIFY), SimplifyParser)
    assert isinstance(get_parser(SourceName.SPEEDYAPPLY), SpeedyApplyParser)


def test_parser_registry_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="unsupported source parser"):
        get_parser("unknown")  # type: ignore[arg-type]
