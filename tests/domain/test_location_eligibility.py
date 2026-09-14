import pytest

from gradradar.domain.location_eligibility import LocationEligibility, classify_us_location


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("New York, NY, USA", LocationEligibility.ELIGIBLE),
        ("Toronto, Canada", LocationEligibility.INELIGIBLE),
        ("Remote", LocationEligibility.UNKNOWN),
        ("Toronto, Canada; SF, USA", LocationEligibility.ELIGIBLE),
        ("Poland", LocationEligibility.UNKNOWN),
        ("Austin, TX", LocationEligibility.ELIGIBLE),
    ],
)
def test_location_classification(location: str, expected: LocationEligibility) -> None:
    assert classify_us_location(location) == expected
