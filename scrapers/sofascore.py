"""Scraper Sofascore — API JSON nao-oficial. Fonte prioritaria (RN-12).

A API nao e documentada e pode mudar sem aviso: todo acesso usa .get() com default.
"""

import logging
import time
from typing import Optional

import config
from models.match_data import GameResult, Scorer, TeamData
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
    return GameResult(
        date=date,
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        competition=competition,
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
