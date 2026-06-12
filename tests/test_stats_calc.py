from models.match_data import GameResult
from scrapers import stats_calc

TEAM = "Flamengo"

# mais recente primeiro
GAMES = [
    GameResult(date="2025-06-08", home_team="Flamengo", away_team="A", home_score=2, away_score=1),  # V, btts, o2.5
    GameResult(date="2025-06-01", home_team="B", away_team="Flamengo", home_score=0, away_score=3),  # V, clean, o2.5
    GameResult(date="2025-05-25", home_team="Flamengo", away_team="C", home_score=1, away_score=1),  # E, btts, o1.5
    GameResult(date="2025-05-18", home_team="D", away_team="Flamengo", home_score=2, away_score=0),  # D
    GameResult(date="2025-05-11", home_team="Flamengo", away_team="E", home_score=4, away_score=2),  # V, btts, o3.5
]


def test_form_outcomes():
    outcomes = [g.outcome_for(TEAM) for g in GAMES]
    assert outcomes == ["V", "V", "E", "D", "V"]


def test_goal_stats():
    gs = stats_calc.compute_goal_stats(GAMES, TEAM)
    assert gs.avg_scored == 2.0      # (2+3+1+0+4)/5
    assert gs.avg_conceded == 1.2    # (1+0+1+2+2)/5
    assert gs.btts_pct == 60.0       # 3/5
    assert gs.over_15_pct == 100.0   # todos os 5 jogos tem 2+ gols
    assert gs.over_25_pct == 60.0    # 3, 3, 6 => 3/5
    assert gs.over_35_pct == 20.0    # apenas 4-2
    assert gs.clean_sheets_pct == 20.0


def test_records():
    assert stats_calc.compute_record(GAMES, TEAM, home=True) == "2V 1E 0D"
    assert stats_calc.compute_record(GAMES, TEAM, home=False) == "1V 0E 1D"


def test_streak():
    assert stats_calc.compute_streak(GAMES, TEAM) == "2 vitorias consecutivas"


def test_empty_games():
    gs = stats_calc.compute_goal_stats([], TEAM)
    assert gs.avg_scored is None
    assert stats_calc.compute_record([], TEAM, home=True) is None
    assert stats_calc.compute_streak([], TEAM) is None
