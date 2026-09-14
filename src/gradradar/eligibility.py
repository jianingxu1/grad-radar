from enum import StrEnum


class LocationEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


def classify_us_location(location: str) -> LocationEligibility:
    value = location.lower()
    us = (
        "usa",
        "united states",
        "nyc",
        "new york",
        "san francisco",
        "sf",
        "los angeles",
        "la",
        "remote - us",
        "remote us",
    )
    foreign = ("canada", "uk", "united kingdom", "india", "germany")
    if any(item in value for item in us):
        return LocationEligibility.ELIGIBLE
    if any(item in value for item in foreign):
        return LocationEligibility.INELIGIBLE
    return LocationEligibility.UNKNOWN
