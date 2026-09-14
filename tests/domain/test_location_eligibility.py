import pytest

from app.domain.location_eligibility import LocationEligibility, classify_us_location


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("New York, NY, USA", LocationEligibility.ELIGIBLE),
        ("Toronto, Canada", LocationEligibility.INELIGIBLE),
        ("Remote in Canada", LocationEligibility.INELIGIBLE),
        ("Remote", LocationEligibility.UNKNOWN),
        ("US Remote", LocationEligibility.ELIGIBLE),
        ("Toronto, Canada; SF, USA", LocationEligibility.ELIGIBLE),
        ("Poland", LocationEligibility.INELIGIBLE),
        ("Austin, TX", LocationEligibility.ELIGIBLE),
        ("California", LocationEligibility.ELIGIBLE),
        ("Seattle", LocationEligibility.ELIGIBLE),
        ("Washington, DC", LocationEligibility.ELIGIBLE),
        ("London, United Kingdom", LocationEligibility.INELIGIBLE),
    ],
)
def test_location_classification(location: str, expected: LocationEligibility) -> None:
    assert classify_us_location(location) == expected
