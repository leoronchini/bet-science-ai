import re

from agent.formatter import fmt, render
from agent.predictor import poisson_baseline
from models.match_data import (GameResult, GoalStats, MatchData, Scorer,
                               TeamData)

SECTIONS = [
    "PARTIDA", "FORMA RECENTE", "ESTATISTICAS DE GOLS", "DESEMPENHO CASA/FORA",
    "SEQUENCIAS", "ARTILHEIROS", "H2H", "PREDICAO",
]

FORBIDDEN = ["aposte", "recomend", "analisando"]


def empty_match():
    return MatchData(home_team=TeamData(name="A"), away_team=TeamData(name="B"))


def full_match():
    games = [
        GameResult(date="2025-06-01", home_team="A", away_team="C", home_score=2, away_score=1),
        GameResult(date="2025-05-25", home_team="D", away_team="A", home_score=0, away_score=0),
    ]
    home = TeamData(
        name="A", recent_games=games,
        goal_stats=GoalStats(avg_scored=1.5, avg_conceded=0.8, btts_pct=50.0,
                             over_15_pct=80.0, over_25_pct=50.0, over_35_pct=20.0),
        home_record="5V 2E 1D", away_record="2V 1E 2D",
        current_streak="2 vitorias consecutivas",
        top_scorers=[Scorer(name="Pedro", goals=10)],
    )
    away = TeamData(name="B", goal_stats=GoalStats(avg_scored=1.1, avg_conceded=1.2))
    h2h = [GameResult(date="2024-10-01", home_team="A", away_team="B", home_score=3, away_score=1)]
    return MatchData(home_team=home, away_team=away, h2h=h2h,
                     competition="Brasileirao", sources_used=["sofascore"])


def test_empty_match_renders_all_sections_with_na():
    match = empty_match()
    report = render(match, poisson_baseline(match))
    for section in SECTIONS:
        assert section in report, f"secao ausente: {section}"
    assert "N/A" in report


def test_deterministic_output():
    match = full_match()
    pred = poisson_baseline(match)
    r1 = render(match, pred)
    r2 = render(match, pred)
    # remover linha do rodape com timestamp
    strip = lambda r: "\n".join(l for l in r.splitlines() if not l.startswith("Fontes:"))
    assert strip(r1) == strip(r2)


def test_no_editorial_text():
    match = full_match()
    report = render(match, poisson_baseline(match)).lower()
    for word in FORBIDDEN:
        assert word not in report, f"texto proibido no relatorio: {word}"


def test_sources_in_footer():
    match = full_match()
    report = render(match, poisson_baseline(match))
    assert "Fontes: sofascore" in report


def test_fmt():
    assert fmt(None) == "N/A"
    assert fmt("") == "N/A"
    assert fmt([]) == "N/A"
    assert fmt(1.234, "%") == "1.2%"
    assert fmt("texto") == "texto"
    assert fmt(5) == "5"
