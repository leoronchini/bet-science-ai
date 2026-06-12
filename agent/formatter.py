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


def _confidence_bar(score: int) -> str:
    """Barra visual de confianca: [████████░░] 80%  ALTA"""
    filled = round(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    if score >= 80:
        label = "ALTA"
    elif score >= 50:
        label = "MEDIA"
    else:
        label = "BAIXA"
    return f"[{bar}] {score}%  {label}"


def render(match_data: MatchData, prediction: Prediction) -> str:
    home, away = match_data.home_team, match_data.away_team
    lines: list[str] = []

    # 1. PARTIDA
    lines += _section(f"PARTIDA  |  {home.name} vs {away.name}")
    lines.append(f"  Competicao       : {fmt(match_data.competition)}")
    lines.append(f"  Fase             : {fmt(match_data.stage)}")
    lines.append(f"  Data             : {fmt(match_data.match_date)}")

    # 1b. CONFIANCA DA IA
    lines += _section("CONFIANCA DA IA")
    if prediction.ai_confidence is not None:
        lines.append(f"  {_confidence_bar(prediction.ai_confidence)}")
    else:
        lines.append("  N/A (analise Gemini indisponivel — Poisson puro)")

    # 2. FORMA RECENTE
    lines += _section(f"FORMA RECENTE (ultimos {config.RECENT_GAMES_LIMIT} jogos)")
    lines.append(f"  {home.name:<20}: {_form_counts(home)}")
    lines.append(f"  {away.name:<20}: {_form_counts(away)}")

    # 2b. CONTEXTO (cansaco / calendario)
    lines += _section("CONTEXTO E CALENDARIO")
    for team in (home, away):
        rest = fmt(team.days_rest, " dias") if team.days_rest is not None else "N/A"
        load = fmt(team.matches_30d, " jogos/30d") if team.matches_30d is not None else "N/A"
        lines.append(f"  {team.name:<20}: descanso {rest} | carga {load}")

    # 2c. DESFALQUES E ESCALACAO
    lines += _section("DESFALQUES E ESCALACAO PROVAVEL")
    for team in (home, away):
        lines.append(f"  {team.name}")
        inj = ", ".join(team.injuries) if team.injuries else "N/A"
        sus = ", ".join(team.suspensions) if team.suspensions else "N/A"
        lines.append(f"    Lesionados     : {inj}")
        lines.append(f"    Suspensos      : {sus}")
        if team.probable_lineup:
            lines.append(f"    Escalacao      : {', '.join(team.probable_lineup)}")

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
    if match_data.odds:
        o = match_data.odds
        book = f" ({o.bookmaker})" if o.bookmaker else ""
        lines.append(f"  Odds Mercado     : {o.home:.2f} | {o.draw:.2f} | {o.away:.2f}{book}")
        implied = o.implied_probs()
        if implied:
            lines.append(
                f"  Mercado (s/ vig) : {implied[0]:.1f}% | {implied[1]:.1f}% | {implied[2]:.1f}%"
            )
    lines.append(SEP)

    # 9. ANALISE NARRATIVA
    if prediction.narrative:
        lines += _section("ANALISE IA")
        # quebra o texto em linhas de ~WIDTH chars sem cortar palavras
        words = prediction.narrative.split()
        line_buf: list[str] = []
        char_count = 0
        for word in words:
            if char_count + len(word) + 1 > WIDTH - 2 and line_buf:
                lines.append("  " + " ".join(line_buf))
                line_buf = [word]
                char_count = len(word)
            else:
                line_buf.append(word)
                char_count += len(word) + 1
        if line_buf:
            lines.append("  " + " ".join(line_buf))
        lines.append(SEP)

    # Rodape de rastreabilidade (RNF-03)
    sources = ", ".join(match_data.sources_used) if match_data.sources_used else "N/A"
    lines.append(f"Fontes: {sources} | Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(lines)
