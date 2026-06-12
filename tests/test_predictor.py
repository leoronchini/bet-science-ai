import pytest

import config
from agent.agent import _validate
from agent.predictor import poisson_baseline
from models.match_data import (GameResult, GoalStats, MatchData, Prediction,
                               Scorer, TeamData)


def make_match(avg_home=1.8, avg_away=1.1):
    home = TeamData(
        name="Time A",
        goal_stats=GoalStats(avg_scored=avg_home, avg_conceded=1.0),
        top_scorers=[Scorer(name="Pedro", goals=12)],
    )
    away = TeamData(
        name="Time B",
        goal_stats=GoalStats(avg_scored=avg_away, avg_conceded=1.4),
        top_scorers=[Scorer(name="Endrick", goals=9)],
    )
    return MatchData(home_team=home, away_team=away)


@pytest.mark.parametrize("avg_h", [0.3, 1.0, 1.8, 2.7, 3.5])
@pytest.mark.parametrize("avg_a", [0.3, 1.3, 3.5])
def test_percentages_sum_to_100(avg_h, avg_a):
    p = poisson_baseline(make_match(avg_h, avg_a))
    assert p.win_home_pct + p.draw_pct + p.win_away_pct == pytest.approx(100, abs=0.01)
    assert p.win_home_pct >= 0 and p.draw_pct >= 0 and p.win_away_pct >= 0


def test_stronger_home_team_favored():
    p = poisson_baseline(make_match(avg_home=2.5, avg_away=0.8))
    assert p.win_home_pct > p.win_away_pct


def test_empty_match_data_no_crash():
    match = MatchData(home_team=TeamData(name="A"), away_team=TeamData(name="B"))
    p = poisson_baseline(match)
    assert p.xg_home is None and p.xg_away is None
    assert p.win_home_pct + p.draw_pct + p.win_away_pct == pytest.approx(100, abs=0.01)


def test_top_scores_has_three():
    p = poisson_baseline(make_match())
    assert len(p.top_scores) == 3


def test_gemini_adjustment_clamped():
    match = make_match()
    base = poisson_baseline(match)
    # Gemini tenta um ajuste exagerado (+30 p.p. no mandante)
    data = {
        "win_home_pct": base.win_home_pct + 30,
        "draw_pct": max(base.draw_pct - 15, 0),
        "win_away_pct": max(base.win_away_pct - 15, 0),
    }
    result = _validate(data, base, match)
    assert result.win_home_pct <= base.win_home_pct + config.AI_MAX_ADJUSTMENT + 1
    assert result.win_home_pct + result.draw_pct + result.win_away_pct == pytest.approx(100, abs=0.1)


def test_unknown_scorer_filtered():
    match = make_match()
    base = poisson_baseline(match)
    data = {
        "win_home_pct": base.win_home_pct,
        "draw_pct": base.draw_pct,
        "win_away_pct": base.win_away_pct,
        "likely_scorers": ["Jogador Inventado (XYZ)", "Pedro (TA)"],
    }
    result = _validate(data, base, match)
    assert result.likely_scorers == ["Pedro (TA)"]


def test_invalid_gemini_response_returns_base():
    match = make_match()
    base = poisson_baseline(match)
    assert _validate({}, base, match) is base
    assert _validate({"win_home_pct": "abc"}, base, match) is base
