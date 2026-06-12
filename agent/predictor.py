"""Motor de predicao em camadas (foco: Copa do Mundo 2026).

Pipeline:
1. Dixon-Coles ajustado (MLE c/ decaimento temporal) sobre os jogos coletados;
   fallback para Poisson simples se faltarem dados.
2. Fatores de contexto: mando real (apenas anfitrioes), cansaco/calendario,
   fase mata-mata, artilheiros lesionados/suspensos.
3. Blend do 1X2 com as probabilidades implicitas das odds de mercado (sem vig).
4. Refinamento Gemini (clamp +-10 p.p.).
"""

import logging
import math
from typing import Optional

import config
from agent import dixon_coles
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


def _short(name: str) -> str:
    return "".join(w[0] for w in name.split()[:3]).upper() if " " in name else name[:3].upper()


def _prediction_from_grid(
    matrix: dict[tuple[int, int], float],
    match: MatchData,
    lam_home: Optional[float],
    lam_away: Optional[float],
) -> Prediction:
    """Constroi a Prediction a partir de uma matriz de placares normalizada."""
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

    likely_scorers = []
    for team in (match.home_team, match.away_team):
        available = [
            s for s in team.top_scorers
            if not any(
                s.name.lower() in absent.lower() or absent.lower() in s.name.lower()
                for absent in team.injuries + team.suspensions
            )
        ]
        if available:
            likely_scorers.append(f"{available[0].name} ({_short(team.name)})")

    return Prediction(
        xg_home=round(lam_home, 2) if lam_home is not None else None,
        xg_away=round(lam_away, 2) if lam_away is not None else None,
        win_home_pct=win_home,
        draw_pct=draw,
        win_away_pct=win_away,
        top_scores=top_scores,
        over_25_pct=over_25,
        btts_pct=btts,
        likely_scorers=likely_scorers,
    )


def poisson_baseline(match: MatchData) -> Prediction:
    """Baseline Poisson independente (fallback e referencia dos testes)."""
    lam_home, home_has_data = _lambda_for(match.home_team, match.away_team)
    lam_away, away_has_data = _lambda_for(match.away_team, match.home_team)
    lam_home *= config.HOME_ADVANTAGE
    lam_away *= config.AWAY_PENALTY

    matrix = dixon_coles.score_grid(lam_home, lam_away, rho=0.0)
    pred = _prediction_from_grid(
        matrix, match,
        lam_home if home_has_data else None,
        lam_away if away_has_data else None,
    )
    return pred


# ---------------------------------------------------------------------------
# Fatores de contexto (Copa 2026)
# ---------------------------------------------------------------------------

def _is_host(team: TeamData) -> bool:
    return team.name.lower() in config.HOST_NATIONS


def _absent_scorers(team: TeamData) -> list[str]:
    """Artilheiros do time presentes nas listas de lesao/suspensao."""
    absences = [a.lower() for a in team.injuries + team.suspensions]
    out = []
    for s in team.top_scorers[: config.TOP_SCORERS_LIMIT]:
        if any(s.name.lower() in a or a in s.name.lower() for a in absences):
            out.append(s.name)
    return out


def _context_factors(match: MatchData) -> tuple[float, float, list[str]]:
    """Fatores multiplicativos sobre (lambda_home, lambda_away) + notas de log."""
    f_home, f_away, notes = 1.0, 1.0, []

    # mando de campo: na Copa 2026 so vale para selecoes anfitrias
    if config.WORLD_CUP_MODE:
        if _is_host(match.home_team):
            f_home *= config.HOME_ADVANTAGE
            notes.append(f"{match.home_team.name} anfitriao (+mando)")
    else:
        f_home *= config.HOME_ADVANTAGE
        f_away *= config.AWAY_PENALTY

    # cansaco: pouco descanso ou calendario congestionado
    for team, attr in ((match.home_team, "f_home"), (match.away_team, "f_away")):
        factor = 1.0
        if team.days_rest is not None and team.days_rest <= config.FATIGUE_SHORT_REST_DAYS:
            factor *= config.FATIGUE_PENALTY
            notes.append(f"{team.name} com {team.days_rest}d de descanso (fadiga)")
        if team.matches_30d is not None and team.matches_30d >= config.CONGESTION_GAMES_30D:
            factor *= config.CONGESTION_PENALTY
            notes.append(f"{team.name} com {team.matches_30d} jogos/30d (congestao)")
        if attr == "f_home":
            f_home *= factor
        else:
            f_away *= factor

    # importancia: mata-mata reduz gols esperados (cautela tatica)
    stage = (match.stage or "").lower()
    if stage and any(k in stage for k in config.KNOCKOUT_STAGES):
        f_home *= config.KNOCKOUT_GOAL_DAMPING
        f_away *= config.KNOCKOUT_GOAL_DAMPING
        notes.append(f"fase {match.stage} (mata-mata: -gols)")

    # desfalques de artilheiros
    for team, is_home in ((match.home_team, True), (match.away_team, False)):
        absent = _absent_scorers(team)
        if absent:
            penalty = config.ABSENT_SCORER_PENALTY ** min(len(absent), 2)
            if is_home:
                f_home *= penalty
            else:
                f_away *= penalty
            notes.append(f"{team.name} sem {', '.join(absent[:2])} (desfalque)")

    return f_home, f_away, notes


def _blend_market(pred: Prediction, match: MatchData) -> Prediction:
    """Blend do 1X2 com as probabilidades implicitas das odds (vig removido)."""
    if match.odds is None:
        return pred
    implied = match.odds.implied_probs()
    if implied is None:
        return pred
    w = config.MARKET_BLEND_WEIGHT
    blended = [
        (1 - w) * model + w * market
        for model, market in zip(
            (pred.win_home_pct, pred.draw_pct, pred.win_away_pct), implied
        )
    ]
    total = sum(blended)
    vals = [round(100 * b / total, 1) for b in blended]
    diff = round(100.0 - sum(vals), 1)
    vals[vals.index(max(vals))] = round(vals[vals.index(max(vals))] + diff, 1)
    pred.win_home_pct, pred.draw_pct, pred.win_away_pct = vals
    logger.info("1X2 apos blend de mercado (peso %.0f%%): %s", w * 100, vals)
    return pred


def advanced_baseline(match: MatchData) -> Prediction:
    """Dixon-Coles + contexto + odds. Fallback transparente para Poisson."""
    pool = list(match.home_team.recent_games) + list(match.away_team.recent_games) + list(match.h2h)
    fit = dixon_coles.fit(match.home_team.name, match.away_team.name, pool)

    if fit is None:
        lam_home, home_has = _lambda_for(match.home_team, match.away_team)
        lam_away, away_has = _lambda_for(match.away_team, match.home_team)
        rho = 0.0
    else:
        lam_home, lam_away, rho = fit.lambda_home, fit.lambda_away, fit.rho
        home_has = away_has = True

    f_home, f_away, notes = _context_factors(match)
    lam_home *= f_home
    lam_away *= f_away
    for note in notes:
        logger.info("Contexto: %s", note)

    matrix = dixon_coles.score_grid(lam_home, lam_away, rho)
    pred = _prediction_from_grid(
        matrix, match,
        lam_home if home_has else None,
        lam_away if away_has else None,
    )
    return _blend_market(pred, match)


def predict(match_data: MatchData) -> Prediction:
    base = advanced_baseline(match_data)
    try:
        from agent.agent import StatsAgent

        return StatsAgent().analyze(match_data, base)
    except Exception as exc:
        logger.warning("Refinamento Gemini indisponivel (%s) — usando modelo estatistico puro", exc)
        return base
