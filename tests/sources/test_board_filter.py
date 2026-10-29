from copy import deepcopy

import pytest

from app.sources.ats import BoardJob
from app.sources.board_filter import (
    DEFAULT_FILTER,
    matches_board_filter,
    normalize_board_jobs,
    validate_filter,
)


def job(**changes: object) -> BoardJob:
    fields = {
        "posting_id": "abc",
        "title": "Software Engineer, New Grad",
        "location": "San Francisco, CA",
        "apply_url": "https://jobs.lever.co/palantir/abc/apply",
        "description": "",
        "department": "Engineering",
        "employment_type": "Full-time",
        "listed_at": None,
        "country": "US",
    }
    fields.update(changes)
    return BoardJob(**fields)  # type: ignore[arg-type]


def test_default_filter_accepts_us_new_grad_software_role() -> None:
    assert matches_board_filter(job(), DEFAULT_FILTER)
    postings = normalize_board_jobs([job()], "lever:palantir", DEFAULT_FILTER, "Palantir")
    assert len(postings) == 1
    assert postings[0].source_name == "lever:palantir"


def test_default_filter_accepts_shield_ai_new_graduate_titles() -> None:
    assert matches_board_filter(
        job(
            title="Software Development Engineer - New Graduate",
            employment_type="Full Time Employee",
        ),
        DEFAULT_FILTER,
    )
    assert matches_board_filter(
        job(
            title="Engineer I, Software Integration - New Grad",
            employment_type="Full Time Employee",
        ),
        DEFAULT_FILTER,
    )


def test_default_filter_accepts_openai_emerging_talent_role() -> None:
    assert matches_board_filter(
        job(
            posting_id="55150071-fce8-48f5-aea4-14ed78b83511",
            title="Software Engineer, Applied Emerging Talent (2027)",
            location="San Francisco",
            country="United States",
            employment_type="FullTime",
        ),
        DEFAULT_FILTER,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "Senior Software Engineer, New Grad"},
        {"title": "Software Engineer"},
        {"title": "Product Manager, New Grad"},
        {"title": "Software Engineer Intern, New Grad"},
        {"location": "London, UK", "country": "GB"},
        {"employment_type": "Intern"},
    ],
)
def test_default_filter_rejects_unrelated_or_uncertain_role(changes: dict) -> None:
    assert not matches_board_filter(job(**changes), DEFAULT_FILTER)


def test_editable_level_terms_change_match() -> None:
    config = deepcopy(DEFAULT_FILTER)
    config["level_terms"] = ["graduate engineer"]
    assert not matches_board_filter(job(), validate_filter(config))
    assert matches_board_filter(job(title="Software Engineer, Graduate Engineer"), config)


def test_invalid_filter_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_filter({"role_terms": ["engineer"]})
