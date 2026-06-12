import pytest

from agent.parser import ParseError, parse_match_input


@pytest.mark.parametrize(
    "raw,home,away",
    [
        ("Brasil vs Argentina", "Brasil", "Argentina"),
        ("Brasil vs. Argentina", "Brasil", "Argentina"),
        ("brasil x argentina", "brasil", "argentina"),
        ("Brasil X Argentina", "Brasil", "Argentina"),
        ("Real Madrid - Barcelona", "Real Madrid", "Barcelona"),
        ("Brasil v Argentina", "Brasil", "Argentina"),
        ("Brasil contra Argentina", "Brasil", "Argentina"),
        ("  Brasil   vs   Argentina  ", "Brasil", "Argentina"),
    ],
)
def test_valid_inputs(raw, home, away):
    parsed = parse_match_input(raw)
    assert parsed.home_team == home
    assert parsed.away_team == away


def test_internal_hyphen_not_separator():
    parsed = parse_match_input("São Paulo vs. Atlético-MG")
    assert parsed.home_team == "São Paulo"
    assert parsed.away_team == "Atlético-MG"


@pytest.mark.parametrize("raw", ["", "   ", "Flamengo", "a vs b vs c", "A vs B"])
def test_invalid_inputs(raw):
    with pytest.raises(ParseError):
        parse_match_input(raw)
