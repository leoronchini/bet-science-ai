"""Funcoes puras de derivacao de estatisticas a partir de listas de jogos.

Compartilhadas por todos os scrapers — nao duplicar este calculo.
Jogos devem vir ordenados do mais recente para o mais antigo.
"""

from typing import Optional

from models.match_data import GameResult, GoalStats


def _goals_for_against(game: GameResult, team: str) -> tuple[int, int]:
    if game.home_team.lower() == team.lower():
        return game.home_score, game.away_score
    return game.away_score, game.home_score


def compute_goal_stats(games: list[GameResult], team: str) -> GoalStats:
    if not games:
        return GoalStats()
    n = len(games)
    scored = conceded = btts = o15 = o25 = o35 = clean = 0
    for g in games:
        gf, ga = _goals_for_against(g, team)
        total = gf + ga
        scored += gf
        conceded += ga
        btts += 1 if (gf > 0 and ga > 0) else 0
        o15 += 1 if total > 1.5 else 0
        o25 += 1 if total > 2.5 else 0
        o35 += 1 if total > 3.5 else 0
        clean += 1 if ga == 0 else 0
    pct = lambda c: round(100.0 * c / n, 1)
    return GoalStats(
        avg_scored=round(scored / n, 2),
        avg_conceded=round(conceded / n, 2),
        btts_pct=pct(btts),
        over_15_pct=pct(o15),
        over_25_pct=pct(o25),
        over_35_pct=pct(o35),
        clean_sheets_pct=pct(clean),
    )


def compute_record(games: list[GameResult], team: str, *, home: bool) -> Optional[str]:
    """Record 'xV yE zD' filtrando jogos por mando. None se nao houver jogos."""
    team_lower = team.lower()
    filtered = [g for g in games if (g.home_team.lower() == team_lower) == home]
    if not filtered:
        return None
    counts = {"V": 0, "E": 0, "D": 0}
    for g in filtered:
        counts[g.outcome_for(team)] += 1
    return f"{counts['V']}V {counts['E']}E {counts['D']}D"


def compute_streak(games: list[GameResult], team: str) -> Optional[str]:
    """Sequencia atual (jogos mais recentes primeiro). Ex: '3 vitorias consecutivas'."""
    if not games:
        return None
    labels = {"V": ("vitoria", "vitorias"), "E": ("empate", "empates"), "D": ("derrota", "derrotas")}
    first = games[0].outcome_for(team)
    count = 0
    for g in games:
        if g.outcome_for(team) == first:
            count += 1
        else:
            break
    singular, plural = labels[first]
    word = singular if count == 1 else plural
    suffix = "consecutiva" if count == 1 else "consecutivas"
    if first == "E":
        suffix = "consecutivo" if count == 1 else "consecutivos"
    return f"{count} {word} {suffix}" if count > 1 else f"1 {singular}"
