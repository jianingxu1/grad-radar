from datetime import UTC, datetime

from app.sources.parsers import parse_simplify, parse_speedyapply


def test_speedyapply_parser_maps_headers_and_posting_link() -> None:
    text = "\n".join(
        [
            "# 2027 USA SWE New Graduate Positions",
            "### FAANG+",
            "| Company | Position | Location | Posting | Age |",
            "| --- | --- | --- | --- | --- |",
            "| Acme | SWE | Seattle, WA | [Apply](https://jobs.example.com/1) | 3d |",
        ]
    )
    result = parse_speedyapply(text, datetime(2026, 1, 3, tzinfo=UTC))
    assert result.postings[0].location == "Seattle, WA"
    assert result.postings[0].apply_url == "https://jobs.example.com/1"


def test_simplify_parser_selects_apply_link_and_us_row() -> None:
    rows = [
        "## 💻 Software Engineering New Grad Roles",
        "<table><tr><th>Company</th><th>Role</th><th>Location</th><th>Application</th><th>Age</th></tr>",
        "<tr><td>Acme</td><td>SWE</td><td>NYC, USA</td>"  # noqa: E501
        '<td><a href="https://jobs.example.com/1"><img alt="Apply" /></a></td><td>2d</td></tr>',
        "<tr><td>Else</td><td>SWE</td><td>Canada</td>"  # noqa: E501
        '<td><a href="https://jobs.example.com/2"><img alt="Apply" /></a></td>'
        "<td>2d</td></tr></table>",
        "Inactive roles",
    ]
    text = "\n".join(rows)
    result = parse_simplify(text, datetime(2026, 1, 3, tzinfo=UTC))
    assert [posting.company_name for posting in result.postings] == ["Acme"]
    assert result.ineligible == 1
