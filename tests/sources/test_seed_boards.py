import json
from collections import Counter
from pathlib import Path

from app.sources.ats import parse_ashby, parse_greenhouse, parse_lever
from app.sources.board_filter import DEFAULT_FILTER, matches_board_filter
from app.sources.seed_boards import SEED_BOARDS

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_seed_boards_are_distinct_and_cover_all_four_platforms() -> None:
    assert len(SEED_BOARDS) == len({board.name for board in SEED_BOARDS}) == 78
    assert Counter(board.platform for board in SEED_BOARDS) == {
        "greenhouse": 33,
        "ashby": 40,
        "lever": 4,
        "oracle": 1,
    }


def test_saved_public_board_responses_have_expected_shapes() -> None:
    greenhouse = parse_greenhouse(json.loads((FIXTURES / "greenhouse_board.json").read_text()))
    ashby = parse_ashby(json.loads((FIXTURES / "ashby_board.json").read_text()))
    lever = parse_lever(json.loads((FIXTURES / "lever_board.json").read_text()))
    assert len(greenhouse) == len(ashby) == len(lever) == 1
    assert matches_board_filter(greenhouse[0], DEFAULT_FILTER)
    assert matches_board_filter(lever[0], DEFAULT_FILTER)
    assert ashby[0].apply_url.startswith("https://jobs.ashbyhq.com/openai/")
