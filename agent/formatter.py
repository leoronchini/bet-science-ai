"""Relatorio padronizado — template fixo, saida deterministica (RNF-04).

Unico ponto que materializa N/A. Zero texto editorial (RF-17, RN-06/07).
"""

from datetime import datetime

import config
from models.match_data import MatchData, Prediction, TeamData

WIDTH = 51
SEP = "═" * WIDTH


def fmt(value, suffix: str = "") -> str:
    """None -> 'N/A'; float -> 1 casa decimal; senao str(value)."""
    if value is None or value == "" or value == []:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def _section(title: str) -> list[str]:
    return [SEP, f"  {title}", SEP]


def _form_counts(team: TeamData) -> str:
    form = team.form_string
    if not form:
        return "N/A"
    v, e, d = form.count("V"), form.count("E"), form.count("D")
    total = len(form)
    return f"{form}  ({v}V {e}E {d}D — {100 * v // total}% vitorias)"


def render(match_data: MatchData, prediction: Prediction) -> str:
    home, away = match_data.home_team, match_data.away_team
    lines: list[str] = []

    # 1. PARTIDA
    lines += _section(f"PARTIDA  |  {home.name} vs {away.name}")
    lines.append(f"  Competicao       : {fmt(match_data.competition)}")
    lines.append(f"  Data             : {fmt(match_data.match_date)}")

    # 2. FORMA RECENTE
    lines += _section("FORMA RECENTE (ultimos 10 jogos)")
    lines.append(f"  {home.name:<20}: {_form_counts(home)}")
    lines.append(f"  {away.name:<20}: {_form_counts(away)}")

    # 3. ESTATISTICAS DE GOLS
    lines += _section("ESTATISTICAS DE GOLS")
    for team in (home, away):
        gs = team.goal_stats
        lines.append(f"  {team.name}")
        lines.append(f"    Gols marcados  : {fmt(gs.avg_scored)} | Sofridos: {fmt(gs.avg_conceded)}")
        lines.append(
            f"    BTTS: {fmt(gs.btts_pct, '%')} | O1.5: {fmt(gs.over_15_pct, '%')}"
            f" | O2.5: {fmt(gs.over_25_pct, '%')} | O3.5: {fmt(gs.over_35_pct, '%')}"
        )

    # 4. DESEMPENHO CASA/FORA
    lines += _section("DESEMPENHO CASA/FORA")
    lines.append(f"  {home.name} (casa)  : {fmt(home.home_record)}")
    lines.append(f"  {away.name} (fora)  : {fmt(away.away_record)}")

    # 5. SEQUENCIAS
    lines += _section("SEQUENCIAS (STREAKS)")
    lines.append(f"  {home.name:<20}: {fmt(home.current_streak)}")
    lines.append(f"  {away.name:<20}: {fmt(away.current_streak)}")

    # 6. ARTILHEIROS
    lines += _section("ARTILHEIROS")
    for team in (home, away):
        lines.append(f"  {team.name}")
        if team.top_scorers:
            for s in team.top_scorers[: config.TOP_SCORERS_LIMIT]:
                lines.append(f"    {s.name} — {s.goals} gols")
        else:
            lines.append("    N/A")

    # 7. H2H
    lines += _section("H2H (confrontos diretos)")
    if match_data.h2h:
        for g in match_data.h2h[: config.H2H_LIMIT]:
            lines.append(f"  {fmt(g.date):<12}| {g.home_team} {g.home_score}-{g.away_score} {g.away_team}")
    else:
        lines.append("  N/A")

    # 8. PREDICAO
    lines += _section(f"PREDICAO  |  {home.name} vs {away.name}")
    lines.append(f"  xG Esperado      : {home.name} {fmt(prediction.xg_home)} | {away.name} {fmt(prediction.xg_away)}")
    lines.append(
        f"  Resultado        : Vitoria {home.name} {fmt(prediction.win_home_pct, '%')}"
        f" | Empate {fmt(prediction.draw_pct, '%')} | {away.name} {fmt(prediction.win_away_pct, '%')}"
    )
    if prediction.top_scores:
        scores = " | ".join(f"{s.score} ({s.probability:.0f}%)" for s in prediction.top_scores)
    else:
        scores = "N/A"
    lines.append(f"  Placar Provavel  : {scores}")
    lines.append(
        f"  Total de Gols    : Over 2.5 ({fmt(prediction.over_25_pct, '%')})"
        f" | BTTS ({fmt(prediction.btts_pct, '%')})"
    )
    likely = " | ".join(prediction.likely_scorers) if prediction.likely_scorers else "N/A"
    lines.append(f"  Artilheiro       : {likely}")
    lines.append(SEP)

    # Rodape de rastreabilidade (RNF-03)
    sources = ", ".join(match_data.sources_used) if match_data.sources_used else "N/A"
    lines.append(f"Fontes: {sources} | Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(lines)
