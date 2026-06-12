"""Testes do modelo Dixon-Coles e do pipeline avancado de predicao."""

from datetime import date, timedelta

import pytest

import config
from agent import dixon_coles, predictor
from models.match_data import (
    GameResult,
    GoalStats,
    MarketOdds,
    MatchData,
    Scorer,
    TeamData,
)

TODAY = date(2026, 6, 12)


def _game(days_ago: int, home: str, away: str, hs: int, as_: int) -> GameResult:
    d = (TODAY - timedelta(days=days_ago)).isoformat()
    return GameResult(date=d, home_team=home, away_team=away, home_score=hs, away_score=as_)


def make_pool() -> list[GameResult]:
    """Brasil forte (goleia), Suica fraca (perde), adversarios variados."""
    games = []
    for i in range(8):
        games.append(_game(7 * i + 3, "Brasil", f"Rival{i}", 3, 0))
        games.append(_game(7 * i + 5, f"Rival{i}", "Suica", 2, 0))
    return games


def test_fit_stronger_team_gets_higher_lambda():
    fit = dixon_coles.fit("Brasil", "Suica", make_pool(), today=TODAY)
    assert fit is not None
    assert fit.lambda_home > fit.lambda_away
    assert fit.n_games == 16
    assert config.DC_RHO_MIN <= fit.rho <= config.DC_RHO_MAX


def test_fit_insufficient_games_returns_none():
    pool = make_pool()[:4]  # < DC_MIN_GAMES
    assert dixon_coles.fit("Brasil", "Suica", pool, today=TODAY) is None


def test_fit_team_not_in_pool_returns_none():
    assert dixon_coles.fit("Marte FC", "Suica", make_pool(), today=TODAY) is None


def test_score_grid_normalized_and_tau_applied():
    grid_indep = dixon_coles.score_grid(1.2, 1.0, rho=0.0)
    grid_dc = dixon_coles.score_grid(1.2, 1.0, rho=-0.15)
    assert sum(grid_indep.values()) == pytest.approx(1.0)
    assert sum(grid_dc.values()) == pytest.approx(1.0)
    # rho negativo: tau(0,0) = 1 - lam*mu*rho > 1 → mais massa no 0-0
    assert grid_dc[(0, 0)] > grid_indep[(0, 0)]


def test_time_decay_recent_games_weigh_more():
    w_recent = dixon_coles._game_weight((TODAY - timedelta(days=5)).isoformat(), TODAY)
    w_old = dixon_coles._game_weight((TODAY - timedelta(days=200)).isoformat(), TODAY)
    assert w_recent > w_old


def make_match(pool: list[GameResult] | None = None) -> MatchData:
    pool = pool if pool is not None else make_pool()
    home = TeamData(
        name="Brasil",
        recent_games=[g for g in pool if "Brasil" in (g.home_team, g.away_team)],
        goal_stats=GoalStats(avg_scored=3.0, avg_conceded=0.0),
        top_scorers=[Scorer(name="Vinicius Junior", goals=5)],
    )
    away = TeamData(
        name="Suica",
        recent_games=[g for g in pool if "Suica" in (g.home_team, g.away_team)],
        goal_stats=GoalStats(avg_scored=0.0, avg_conceded=2.0),
        top_scorers=[Scorer(name="Granit Xhaka", goals=2)],
    )
    return MatchData(home_team=home, away_team=away)


def test_advanced_baseline_sums_100():
    pred = predictor.advanced_baseline(make_match())
    total = pred.win_home_pct + pred.draw_pct + pred.win_away_pct
    assert total == pytest.approx(100, abs=0.1)
    assert pred.win_home_pct > pred.win_away_pct  # Brasil favorito


def test_market_odds_implied_probs_removes_vig():
    odds = MarketOdds(home=1.80, draw=3.60, away=4.50)
    implied = odds.implied_probs()
    assert implied is not None
    assert sum(implied) == pytest.approx(100, abs=0.3)
    assert implied[0] > implied[1] > implied[2]


def test_market_blend_moves_toward_odds():
    match = make_match()
    no_odds = predictor.advanced_baseline(match)
    # mercado discorda: azarao (Suica) com odds de favorito
    match.odds = MarketOdds(home=4.50, draw=3.60, away=1.80)
    with_odds = predictor.advanced_baseline(match)
    assert with_odds.win_away_pct > no_odds.win_away_pct
    assert with_odds.win_home_pct < no_odds.win_home_pct


def test_absent_scorer_reduces_lambda_and_likely_scorers():
    match_full = make_match()
    pred_full = predictor.advanced_baseline(match_full)

    match_injured = make_match()
    match_injured.home_team.injuries = ["Vinicius Junior"]
    pred_injured = predictor.advanced_baseline(match_injured)

    assert pred_injured.xg_home < pred_full.xg_home
    assert all("Vinicius" not in s for s in pred_injured.likely_scorers)


def test_knockout_stage_dampens_goals():
    match_group = make_match()
    pred_group = predictor.advanced_baseline(match_group)

    match_ko = make_match()
    match_ko.stage = "Oitavas de final"
    pred_ko = predictor.advanced_baseline(match_ko)

    assert pred_ko.over_25_pct < pred_group.over_25_pct


def test_fatigue_penalty_applied():
    match_rested = make_match()
    match_rested.home_team.days_rest = 7
    pred_rested = predictor.advanced_baseline(match_rested)

    match_tired = make_match()
    match_tired.home_team.days_rest = 2
    pred_tired = predictor.advanced_baseline(match_tired)

    assert pred_tired.xg_home < pred_rested.xg_home
