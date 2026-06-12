"""Orquestra a cadeia de fontes com prioridade (RN-12) e merge sem sobrescrita.

Cadeia: Sofascore -> Soccerway -> 365scores. xG: somente Understat (RN-14).
Fallback Claude (RN-13): apenas se faltarem campos criticos ao final.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

import config
from agent.parser import ParsedMatch
from models.match_data import MatchData, TeamData
from scrapers import fallback, understat
from scrapers.base import BaseScraper
from scrapers.scores365 import Scores365Scraper
from scrapers.soccerway import SoccerwayScraper
from scrapers.sofascore import SofascoreScraper

logger = logging.getLogger(__name__)


def _merge_team(primary: TeamData, secondary: TeamData) -> None:
    """Copia para `primary` apenas os campos que ele ainda nao tem."""
    if not primary.recent_games and secondary.recent_games:
        primary.recent_games = secondary.recent_games
    gs_p, gs_s = primary.goal_stats, secondary.goal_stats
    for attr in ("avg_scored", "avg_conceded", "btts_pct", "over_15_pct",
                 "over_25_pct", "over_35_pct", "clean_sheets_pct"):
        if getattr(gs_p, attr) is None:
            setattr(gs_p, attr, getattr(gs_s, attr))
    for attr in ("home_record", "away_record", "current_streak"):
        if getattr(primary, attr) is None:
            setattr(primary, attr, getattr(secondary, attr))
    if not primary.top_scorers and secondary.top_scorers:
        primary.top_scorers = secondary.top_scorers


def _is_complete(team: TeamData) -> bool:
    return bool(
        team.recent_games
        and team.goal_stats.avg_scored is not None
        and team.current_streak
        and team.top_scorers
    )


def _collect_team(team_name: str, scrapers: list[BaseScraper], sources_used: list[str]) -> TeamData:
    result: TeamData | None = None
    for scraper in scrapers:
        if result is not None and _is_complete(result):
            break
        logger.info("Tentando fonte %s para %r", scraper.source_name, team_name)
        try:
            data = scraper.fetch_team_data(team_name)
        except Exception:
            logger.exception("Fonte %s lancou excecao inesperada", scraper.source_name)
            data = None
        if data is None:
            logger.warning("Fonte %s sem dados para %r", scraper.source_name, team_name)
            continue
        if result is None:
            result = data
        else:
            _merge_team(result, data)
        if scraper.source_name not in sources_used:
            sources_used.append(scraper.source_name)
    return result or TeamData(name=team_name)


def _fill_xg(team: TeamData, sources_used: list[str]) -> None:
    """xG via Understat, somente para ligas cobertas (RN-14)."""
    competitions = {g.competition for g in team.recent_games if g.competition}
    league_names = {
        "premier league": "EPL", "laliga": "La_liga", "la liga": "La_liga",
        "bundesliga": "Bundesliga", "serie a": "Serie_A", "ligue 1": "Ligue_1",
    }
    in_covered_league = any(
        key in c.lower() for c in competitions for key in league_names
    )
    if not in_covered_league:
        return
    xg = understat.fetch_xg(team.name)
    if xg:
        team.xg_for, team.xg_against = xg
        if "understat" not in sources_used:
            sources_used.append("understat")


def _missing_critical(match: MatchData) -> list[str]:
    missing = []
    for label, team in (("home", match.home_team), ("away", match.away_team)):
        if not team.recent_games:
            missing.append(f"{label}.recent_games")
        if team.goal_stats.avg_scored is None:
            missing.append(f"{label}.goal_stats")
    return missing


def collect(parsed: ParsedMatch) -> MatchData:
    scrapers: list[BaseScraper] = [SofascoreScraper()]
    if config.ENABLE_365SCORES:
        scrapers.append(Scores365Scraper())
    scrapers.append(SoccerwayScraper())

    sources_used: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        home_future = pool.submit(_collect_team, parsed.home_team, scrapers, sources_used)
        away_future = pool.submit(_collect_team, parsed.away_team, scrapers, sources_used)
        home = home_future.result(timeout=config.SCRAPER_TIMEOUT)
        away = away_future.result(timeout=config.SCRAPER_TIMEOUT)

    match = MatchData(home_team=home, away_team=away, sources_used=sources_used)

    for team in (home, away):
        _fill_xg(team, sources_used)

    for scraper in scrapers:
        try:
            h2h = scraper.fetch_h2h(home, away)
        except Exception:
            logger.exception("H2H falhou na fonte %s", scraper.source_name)
            h2h = []
        if h2h:
            match.h2h = h2h
            break

    competitions = [g.competition for g in home.recent_games if g.competition]
    if competitions:
        match.competition = competitions[0]

    missing = _missing_critical(match)
    if missing:
        logger.info("Campos criticos faltantes %s — acionando fallback Claude", missing)
        match = fallback.fill_missing(match, missing)

    return match
