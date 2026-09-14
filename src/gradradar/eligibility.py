import re
from enum import StrEnum


class LocationEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


def classify_us_location(location: str) -> LocationEligibility:
    value = location.lower().strip()
    tokens = set(re.findall(r"[a-z]{2,}", value))
    state_codes = {
        "al",
        "ak",
        "az",
        "ar",
        "ca",
        "co",
        "ct",
        "de",
        "fl",
        "ga",
        "hi",
        "id",
        "il",
        "in",
        "ia",
        "ks",
        "ky",
        "la",
        "me",
        "md",
        "ma",
        "mi",
        "mn",
        "ms",
        "mo",
        "mt",
        "ne",
        "nv",
        "nh",
        "nj",
        "nm",
        "ny",
        "nc",
        "nd",
        "oh",
        "ok",
        "or",
        "pa",
        "ri",
        "sc",
        "sd",
        "tn",
        "tx",
        "ut",
        "vt",
        "va",
        "wa",
        "wv",
        "wi",
        "wy",
        "dc",
    }
    us_phrases = ("usa", "united states", "new york", "san francisco", "los angeles")
    if (
        tokens & state_codes
        or tokens & {"nyc", "sf"}
        or any(phrase in value for phrase in us_phrases)
    ):
        return LocationEligibility.ELIGIBLE
    if any(item in value for item in ("canada", "uk", "united kingdom", "india", "germany")):
        return LocationEligibility.INELIGIBLE
    return LocationEligibility.UNKNOWN
