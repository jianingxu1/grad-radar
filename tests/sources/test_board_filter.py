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
    "title",
    [
        "Software Engineer - University Hire 2027",
        "Software Engineer – New College Graduate",
        "Software Engineer | Early Careers, 2027 Start",
        "Campus Software Engineer (Full-Time)",
        "Software Engineer (2027 Grads)",
        "Forward Deployed Engineer - New Grad (2027)",
        "AI Platform Engineer, 2027 New Grad",
        "AI/ML Engineer, 2027 New Grad",
        "Applied AI NCG (Non Silicon)",
        "Software Engineer I, Network",
    ],
)
def test_default_filter_accepts_verified_early_career_title_variants(title: str) -> None:
    assert matches_board_filter(job(title=title), DEFAULT_FILTER)


def test_default_filter_accepts_generic_title_with_graduation_cohort() -> None:
    assert matches_board_filter(
        job(
            title="Software Developer",
            description=(
                "A degree in Computer Science, with graduation expected between "
                "December 2026 and June 2027."
            ),
        ),
        DEFAULT_FILTER,
    )


def test_final_filter_rejects_missing_title_despite_graduation_phrase() -> None:
    assert not matches_board_filter(
        job(title="", description="Graduation expected between 2026 and 2027."), DEFAULT_FILTER
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "Senior Software Engineer, New Grad"},
        {"title": "Software Engineer"},
        {"title": "Software Engineer II"},
        {
            "title": "Software Developer",
            "description": "A degree in Computer Science is preferred.",
        },
        {"title": "Analyst, Early Career (Full Stack)"},
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
    assert not matches_board_filter(
        job(title="Software Developer", description="Graduation expected between 2026 and 2027"),
        config,
    )


def test_invalid_filter_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_filter({"role_terms": ["engineer"]})
