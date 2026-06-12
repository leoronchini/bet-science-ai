"""Modelo Dixon-Coles (1997) — extensao do Poisson usada em betting profissional.

Diferencas sobre o Poisson independente:
1. Forcas de ataque/defesa POR TIME ajustadas por maxima verossimilhanca
   iterativa sobre todos os jogos coletados (nao apenas medias agregadas).
2. Decaimento temporal exponencial: jogos antigos pesam menos no ajuste.
3. Correcao tau de dependencia em placares baixos (0-0, 1-0, 0-1, 1-1),
   a principal fraqueza conhecida do Poisson independente.
4. Regularizacao por pseudo-jogos: times com poucos dados sao encolhidos
   para a media global, evitando forcas extremas por amostra pequena.

Sem dependencias externas — ajuste iterativo + grid search de rho.
"""

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import config
from models.match_data import GameResult

logger = logging.getLogger(__name__)


@dataclass
class DCFit:
    lambda_home: float   # gols esperados do mandante no confronto
    lambda_away: float
    rho: float           # correlacao de placares baixos
    n_games: int         # jogos usados no ajuste
    n_teams: int


def _game_weight(game_date: Optional[str], today: date) -> float:
    """Peso exponencial: exp(-xi * dias_atras)."""
    days = config.DC_DEFAULT_GAME_AGE_DAYS
    if game_date:
        try:
            days = max(0, (today - datetime.strptime(game_date, "%Y-%m-%d").date()).days)
        except ValueError:
            pass
    return math.exp(-config.DC_TIME_DECAY * days)


def _tau(h: int, a: int, lam: float, mu: float, rho: float) -> float:
    """Correcao Dixon-Coles para placares baixos."""
    if h == 0 and a == 0:
        return 1 - lam * mu * rho
    if h == 0 and a == 1:
        return 1 + lam * rho
    if h == 1 and a == 0:
        return 1 + mu * rho
    if h == 1 and a == 1:
        return 1 - rho
    return 1.0


def _poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def score_grid(lam_home: float, lam_away: float, rho: float = 0.0) -> dict[tuple[int, int], float]:
    """Matriz de probabilidades de placar com correcao tau, normalizada."""
    grid = config.MAX_GOALS_GRID
    matrix = {}
    for h in range(grid + 1):
        for a in range(grid + 1):
            p = _poisson(h, lam_home) * _poisson(a, lam_away)
            p *= max(_tau(h, a, lam_home, lam_away, rho), 1e-9)
            matrix[(h, a)] = p
    total = sum(matrix.values())
    return {k: v / total for k, v in matrix.items()}


def _dedupe(games: list[GameResult]) -> list[GameResult]:
    seen: set[tuple] = set()
    out = []
    for g in games:
        key = (g.date, g.home_team.lower(), g.away_team.lower(), g.home_score, g.away_score)
        if key not in seen:
            seen.add(key)
            out.append(g)
    return out


def _fit_strengths(
    games: list[GameResult], weights: list[float]
) -> tuple[dict[str, float], dict[str, float], float]:
    """Ajuste iterativo multiplicativo de ataque/defesa com encolhimento.

    Parametrizacao: lambda = att[mandante] * dfc[visitante].
    `att` em escala de gols; `dfc` normalizada com media 1.
    Retorna (att, dfc, media_de_gols_por_time).
    """
    teams = sorted({g.home_team.lower() for g in games} | {g.away_team.lower() for g in games})
    total_w = sum(weights)
    avg_goals = sum(w * (g.home_score + g.away_score) for g, w in zip(games, weights)) / (2 * total_w)
    k = config.DC_PSEUDO_GAMES  # pseudo-jogos na media (regularizacao)

    att = {t: avg_goals for t in teams}
    dfc = {t: 1.0 for t in teams}

    for _ in range(config.DC_FIT_ITERATIONS):
        # ataque: gols marcados ponderados / exposicao defensiva ponderada
        for t in teams:
            num, den = k * avg_goals, k  # prior
            for g, w in zip(games, weights):
                if g.home_team.lower() == t:
                    num += w * g.home_score
                    den += w * dfc[g.away_team.lower()]
                elif g.away_team.lower() == t:
                    num += w * g.away_score
                    den += w * dfc[g.home_team.lower()]
            att[t] = num / den
        # defesa: gols sofridos ponderados / exposicao ofensiva ponderada
        for t in teams:
            num, den = k * avg_goals, k * avg_goals  # prior -> dfc 1.0
            for g, w in zip(games, weights):
                if g.home_team.lower() == t:
                    num += w * g.away_score
                    den += w * att[g.away_team.lower()]
                elif g.away_team.lower() == t:
                    num += w * g.home_score
                    den += w * att[g.home_team.lower()]
            dfc[t] = num / den
        # identificabilidade: media das defesas = 1
        mean_dfc = sum(dfc.values()) / len(dfc)
        for t in teams:
            dfc[t] /= mean_dfc
            att[t] *= mean_dfc

    return att, dfc, avg_goals


def _fit_rho(
    games: list[GameResult], weights: list[float],
    att: dict[str, float], dfc: dict[str, float],
) -> float:
    """Grid search 1-D de rho maximizando a log-verossimilhanca ponderada."""
    best_rho, best_ll = 0.0, -math.inf
    rho = config.DC_RHO_MIN
    while rho <= config.DC_RHO_MAX + 1e-9:
        ll = 0.0
        for g, w in zip(games, weights):
            lam = att[g.home_team.lower()] * dfc[g.away_team.lower()]
            mu = att[g.away_team.lower()] * dfc[g.home_team.lower()]
            tau = _tau(min(g.home_score, 2), min(g.away_score, 2), lam, mu, rho)
            if tau <= 0:
                ll = -math.inf
                break
            p = _poisson(min(g.home_score, config.MAX_GOALS_GRID), lam) \
                * _poisson(min(g.away_score, config.MAX_GOALS_GRID), mu) * tau
            ll += w * math.log(max(p, 1e-12))
        if ll > best_ll:
            best_ll, best_rho = ll, rho
        rho += config.DC_RHO_STEP
    return round(best_rho, 3)


def fit(
    home_name: str,
    away_name: str,
    games: list[GameResult],
    *,
    today: Optional[date] = None,
) -> Optional[DCFit]:
    """Ajusta o modelo sobre o pool de jogos e retorna os lambdas do confronto.

    Retorna None se nao ha dados suficientes (caller usa o fallback Poisson).
    """
    today = today or date.today()
    games = _dedupe([g for g in games if g.home_score >= 0 and g.away_score >= 0])
    if len(games) < config.DC_MIN_GAMES:
        logger.info("Dixon-Coles: apenas %d jogos (< %d) — fallback Poisson",
                    len(games), config.DC_MIN_GAMES)
        return None

    home_l, away_l = home_name.lower(), away_name.lower()
    in_pool = {g.home_team.lower() for g in games} | {g.away_team.lower() for g in games}
    if home_l not in in_pool or away_l not in in_pool:
        logger.info("Dixon-Coles: %r ou %r sem jogos no pool — fallback Poisson",
                    home_name, away_name)
        return None

    weights = [_game_weight(g.date, today) for g in games]
    att, dfc, _ = _fit_strengths(games, weights)
    rho = _fit_rho(games, weights, att, dfc)

    lam_home = att[home_l] * dfc[away_l]
    lam_away = att[away_l] * dfc[home_l]
    logger.info(
        "Dixon-Coles ajustado: %d jogos, %d times, rho=%.2f, lambdas=(%.2f, %.2f)",
        len(games), len(att), rho, lam_home, lam_away,
    )
    return DCFit(
        lambda_home=lam_home,
        lambda_away=lam_away,
        rho=rho,
        n_games=len(games),
        n_teams=len(att),
    )
