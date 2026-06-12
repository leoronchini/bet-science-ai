"""Motor de predicao: Poisson local como base, Claude para refinamento (AD-02)."""

import logging
import math
from typing import Optional

import config
from models.match_data import MatchData, Prediction, ScorePrediction, TeamData

logger = logging.getLogger(__name__)


def _poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _lambda_for(attacking: TeamData, defending: TeamData) -> tuple[Optional[float], bool]:
    """(lambda, has_data). Prefere xG; senao medias de gols; senao prior global."""
    if attacking.xg_for is not None and defending.xg_against is not None:
        return (attacking.xg_for + defending.xg_against) / 2, True
    atk = attacking.goal_stats.avg_scored
    def_ = defending.goal_stats.avg_conceded
    if atk is not None and def_ is not None:
        return (atk + def_) / 2, True
    if atk is not None:
        return atk, True
    return config.DEFAULT_LAMBDA, False


def poisson_baseline(match: MatchData) -> Prediction:
    lam_home, home_has_data = _lambda_for(match.home_team, match.away_team)
    lam_away, away_has_data = _lambda_for(match.away_team, match.home_team)
    lam_home *= config.HOME_ADVANTAGE
    lam_away *= config.AWAY_PENALTY

    grid = config.MAX_GOALS_GRID
    matrix = {
        (h, a): _poisson(h, lam_home) * _poisson(a, lam_away)
        for h in range(grid + 1)
        for a in range(grid + 1)
    }
    total = sum(matrix.values())  # massa truncada — normalizar
    matrix = {k: v / total for k, v in matrix.items()}

    win_home = sum(p for (h, a), p in matrix.items() if h > a) * 100
    draw = sum(p for (h, a), p in matrix.items() if h == a) * 100
    win_away = sum(p for (h, a), p in matrix.items() if h < a) * 100

    # arredondar e fechar soma exata em 100 ajustando o maior (RN-08)
    vals = [round(win_home, 1), round(draw, 1), round(win_away, 1)]
    diff = round(100.0 - sum(vals), 1)
    vals[vals.index(max(vals))] = round(vals[vals.index(max(vals))] + diff, 1)
    win_home, draw, win_away = vals

    top = sorted(matrix.items(), key=lambda kv: kv[1], reverse=True)[:3]
    top_scores = [
        ScorePrediction(score=f"{h}-{a}", probability=round(p * 100, 1))
        for (h, a), p in top
    ]

    over_25 = round(sum(p for (h, a), p in matrix.items() if h + a >= 3) * 100, 1)
    btts = round(sum(p for (h, a), p in matrix.items() if h >= 1 and a >= 1) * 100, 1)

    def short(name: str) -> str:
        return "".join(w[0] for w in name.split()[:3]).upper() if " " in name else name[:3].upper()

    likely_scorers = []
    for team in (match.home_team, match.away_team):
        if team.top_scorers:
            likely_scorers.append(f"{team.top_scorers[0].name} ({short(team.name)})")

    return Prediction(
        xg_home=round(lam_home, 2) if home_has_data else None,
        xg_away=round(lam_away, 2) if away_has_data else None,
        win_home_pct=win_home,
        draw_pct=draw,
        win_away_pct=win_away,
        top_scores=top_scores,
        over_25_pct=over_25,
        btts_pct=btts,
        likely_scorers=likely_scorers,
    )


def predict(match_data: MatchData) -> Prediction:
    base = poisson_baseline(match_data)
    try:
        from agent.agent import StatsAgent

        return StatsAgent().analyze(match_data, base)
    except Exception as exc:
        logger.warning("Refinamento Gemini indisponivel (%s) — usando Poisson puro", exc)
        return base
