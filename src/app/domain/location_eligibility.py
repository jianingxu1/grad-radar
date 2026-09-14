import re
from enum import StrEnum


class LocationEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


US_STATE_CODES = frozenset(
    {
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
)
US_STATE_NAMES = frozenset(
    {
        "alabama",
        "alaska",
        "arizona",
        "arkansas",
        "california",
        "colorado",
        "connecticut",
        "delaware",
        "florida",
        "georgia",
        "hawaii",
        "idaho",
        "illinois",
        "indiana",
        "iowa",
        "kansas",
        "kentucky",
        "louisiana",
        "maine",
        "maryland",
        "massachusetts",
        "michigan",
        "minnesota",
        "mississippi",
        "missouri",
        "montana",
        "nebraska",
        "nevada",
        "new hampshire",
        "new jersey",
        "new mexico",
        "new york",
        "north carolina",
        "north dakota",
        "ohio",
        "oklahoma",
        "oregon",
        "pennsylvania",
        "rhode island",
        "south carolina",
        "south dakota",
        "tennessee",
        "texas",
        "utah",
        "vermont",
        "virginia",
        "washington",
        "west virginia",
        "wisconsin",
        "wyoming",
        "district of columbia",
    }
)
TECH_HUB_CITIES = frozenset(
    {
        "atlanta",
        "austin",
        "boston",
        "chicago",
        "dallas",
        "denver",
        "houston",
        "los angeles",
        "miami",
        "new york",
        "nyc",
        "raleigh",
        "san diego",
        "san francisco",
        "seattle",
        "sf",
        "silicon valley",
        "washington dc",
    }
)
EXPLICIT_NON_US_LOCATIONS = frozenset(
    {
        "argentina",
        "australia",
        "austria",
        "belgium",
        "brazil",
        "canada",
        "chile",
        "china",
        "czech republic",
        "denmark",
        "finland",
        "france",
        "germany",
        "hong kong",
        "hungary",
        "india",
        "ireland",
        "israel",
        "italy",
        "japan",
        "mexico",
        "netherlands",
        "new zealand",
        "norway",
        "poland",
        "portugal",
        "republic of korea",
        "romania",
        "singapore",
        "south korea",
        "spain",
        "sweden",
        "switzerland",
        "taiwan",
        "turkey",
        "u.k.",
        "uae",
        "uk",
        "ukraine",
        "united arab emirates",
        "united kingdom",
    }
)


def classify_us_location(location: str) -> LocationEligibility:
    value = location.lower().strip()
    if _has_us_signal(value):
        return LocationEligibility.ELIGIBLE
    if _contains_any_phrase(value, EXPLICIT_NON_US_LOCATIONS):
        return LocationEligibility.INELIGIBLE
    return LocationEligibility.UNKNOWN


def _has_us_signal(value: str) -> bool:
    if re.search(r"\b(?:u\.?s\.?a?\.?|united states(?: of america)?)\b", value):
        return True
    if _contains_any_phrase(value, US_STATE_NAMES | TECH_HUB_CITIES):
        return True
    state_tokens = set(re.findall(r"(?:^|[,/])\s*([a-z]{2})\b", value))
    return bool(state_tokens & US_STATE_CODES)


def _contains_any_phrase(value: str, phrases: frozenset[str]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", value) for phrase in phrases)
