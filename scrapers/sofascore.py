"""Scraper Sofascore — API JSON nao-oficial. Fonte prioritaria (RN-12).

A API nao e documentada e pode mudar sem aviso: todo acesso usa .get() com default.
"""

import logging
import time
from typing import Optional

import config
from models.match_data import GameResult, MatchStats, Scorer, TeamData
from scrapers import stats_calc
from scrapers.base import BaseScraper, http_get

logger = logging.getLogger(__name__)

API = "https://api.sofascore.com/api/v1"


def _parse_event(event: dict) -> Optional[GameResult]:
    home = event.get("homeTeam", {}).get("name")
    away = event.get("awayTeam", {}).get("name")
    home_score = event.get("homeScore", {}).get("current")
    away_score = event.get("awayScore", {}).get("current")
    if None in (home, away, home_score, away_score):
        return None
    ts = event.get("startTimestamp")
    date = time.strftime("%Y-%m-%d", time.gmtime(ts)) if ts else None
    competition = event.get("tournament", {}).get("name")
    stats = event.get("_stats") if isinstance(event.get("_stats"), MatchStats) else None
    return GameResult(
        date=date,
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        competition=competition,
        stats=stats,
    )


class SofascoreScraper(BaseScraper):
    source_name = "sofascore"

    def search_team(self, name: str) -> Optional[tuple[int, str]]:
        resp = http_get(f"{API}/search/all?q={name}")
        if resp is None:
            return None
        try:
            results = resp.json().get("results", [])
        except ValueError:
            logger.warning("Sofascore: resposta de busca nao-JSON para %r", name)
            return None
        for item in results:
            entity = item.get("entity", {})
            if item.get("type") == "team" and entity.get("sport", {}).get("slug") == "football":
                return entity.get("id"), entity.get("name", name)
        return None

    def _last_events(self, team_id: int) -> list[dict]:
        resp = http_get(f"{API}/team/{team_id}/events/last/0")
        if resp is None:
            return []
        try:
            return resp.json().get("events", [])
        except ValueError:
            return []

    def fetch_team_data(self, team_name: str) -> Optional[TeamData]:
        found = self.search_team(team_name)
        if not found:
            logger.warning("Sofascore: time %r nao encontrado", team_name)
            return None
        team_id, canonical = found
        time.sleep(0.5)

        events = self._last_events(team_id)
        finished = [e for e in events if e.get("status", {}).get("type") == "finished"]
        self.enrich_events_with_stats(finished)
        # API retorna do mais antigo para o mais recente; invertemos
        finished.reverse()
        games = [g for g in (_parse_event(e) for e in finished) if g]
        games = games[: config.RECENT_GAMES_LIMIT]

        team = TeamData(name=canonical, resolved_id=str(team_id), recent_games=games)
        team.goal_stats = stats_calc.compute_goal_stats(games, canonical)
        team.home_record = stats_calc.compute_record(games, canonical, home=True)
        team.away_record = stats_calc.compute_record(games, canonical, home=False)
        team.current_streak = stats_calc.compute_streak(games, canonical)
        team.top_scorers = self._fetch_top_scorers(team_id, finished)
        return team

    def _fetch_top_scorers(self, team_id: int, finished_events: list[dict]) -> list[Scorer]:
        if not finished_events:
            return []
        last = finished_events[0]
        ut_id = last.get("tournament", {}).get("uniqueTournament", {}).get("id")
        season_id = last.get("season", {}).get("id")
        if not ut_id or not season_id:
            return []
        time.sleep(0.5)
        resp = http_get(
            f"{API}/team/{team_id}/unique-tournament/{ut_id}/season/{season_id}/top-players/overall"
        )
        if resp is None:
            return []
        try:
            entries = resp.json().get("topPlayers", {}).get("goals", [])
        except ValueError:
            return []
        scorers = []
        for entry in entries[: config.TOP_SCORERS_LIMIT]:
            name = entry.get("player", {}).get("name")
            goals = entry.get("statistics", {}).get("goals")
            if name and goals is not None:
                scorers.append(Scorer(name=name, goals=goals))
        return scorers

    def fetch_h2h(self, home: TeamData, away: TeamData) -> list[GameResult]:
        # 1) tentar via proximo confronto agendado
        if home.resolved_id:
            resp = http_get(f"{API}/team/{home.resolved_id}/events/next/0")
            if resp is not None:
                try:
                    events = resp.json().get("events", [])
                except ValueError:
                    events = []
                away_lower = away.name.lower()
                for e in events:
                    names = {
                        e.get("homeTeam", {}).get("name", "").lower(),
                        e.get("awayTeam", {}).get("name", "").lower(),
                    }
                    if away_lower in names:
                        event_id = e.get("id")
                        if event_id:
                            h2h = self._h2h_by_event(event_id)
                            if h2h:
                                return h2h
                        break
        # 2) fallback: cruzar jogos recentes dos dois times
        away_lower = away.name.lower()
        mutual = [
            g
            for g in home.recent_games
            if away_lower in (g.home_team.lower(), g.away_team.lower())
        ]
        return mutual[: config.H2H_LIMIT]

    def fetch_event_statistics(self, event_id: int) -> Optional[MatchStats]:
        """Busca estatisticas detalhadas (escanteios, cartoes, posse, etc)."""
        time.sleep(0.5)
        resp = http_get(f"{API}/event/{event_id}/statistics")
        if resp is None:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None

        groups = []
        for period in data.get("statistics", []):
            if period.get("period") == "ALL":
                groups = period.get("groups", [])
                break

        stats = MatchStats()
        for group in groups:
            items = group.get("statisticsItems", [])
            for item in items:
                name = item.get("name", "")
                home_val = item.get("home")
                away_val = item.get("away")
                try:
                    home_int = int(home_val) if home_val is not None else None
                    away_int = int(away_val) if away_val is not None else None
                    home_float = float(home_val) if home_val is not None else None
                    away_float = float(away_val) if away_val is not None else None
                except (ValueError, TypeError):
                    continue

                if "Corner kicks" in name:
                    stats.escanteios_casa = home_int
                    stats.escanteios_fora = away_int
                elif "Yellow cards" in name:
                    stats.cartoes_amarelos_casa = home_int
                    stats.cartoes_amarelos_fora = away_int
                elif "Red cards" in name:
                    stats.cartoes_vermelhos_casa = home_int
                    stats.cartoes_vermelhos_fora = away_int
                elif "Ball possession" in name:
                    stats.posse_casa = home_float
                    stats.posse_fora = away_float
                elif "Shots on target" in name:
                    stats.chutes_gol_casa = home_int
                    stats.chutes_gol_fora = away_int
                elif "Fouls" in name:
                    stats.faltas_casa = home_int
                    stats.faltas_fora = away_int
                elif "Offsides" in name:
                    stats.impedimentos_casa = home_int
                    stats.impedimentos_fora = away_int

        has_data = any([
            stats.escanteios_casa, stats.cartoes_amarelos_casa,
            stats.cartoes_vermelhos_casa, stats.posse_casa,
        ])
        return stats if has_data else None

    def enrich_events_with_stats(self, events: list[dict]) -> None:
        """Enriquece eventos finalizados com MatchStats in-place."""
        for event in events:
            if event.get("status", {}).get("type") != "finished":
                continue
            event_id = event.get("id")
            if not event_id:
                continue
            stats = self.fetch_event_statistics(event_id)
            if stats:
                event["_stats"] = stats

    def _h2h_by_event(self, event_id: int) -> list[GameResult]:
        time.sleep(0.5)
        resp = http_get(f"{API}/event/{event_id}/h2h/events")
        if resp is None:
            return []
        try:
            events = resp.json().get("events", [])
        except ValueError:
            return []
        events.reverse()  # mais recente primeiro
        games = [g for g in (_parse_event(e) for e in events) if g]
        return games[: config.H2H_LIMIT]
