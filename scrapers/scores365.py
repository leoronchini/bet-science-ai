"""Scraper 365scores — API JSON interna (webws.365scores.com), HTTP puro.

Descoberta na validacao: a API interna da SPA responde a requests diretos,
dispensando o Playwright. Endpoints nao documentados — acesso defensivo via .get().
"""

import logging
import time
from typing import Optional

import config
from models.match_data import GameResult, TeamData
from scrapers import stats_calc
from scrapers.base import BaseScraper, http_get

logger = logging.getLogger(__name__)

BASE = "https://webws.365scores.com/web"
COMMON = "appTypeId=5&langId=31&timezoneName=America/Sao_Paulo&userCountryId=21"


def _parse_game(game: dict) -> Optional[GameResult]:
    home = game.get("homeCompetitor", {})
    away = game.get("awayCompetitor", {})
    h_name, a_name = home.get("name"), away.get("name")
    h_score, a_score = home.get("score"), away.get("score")
    if None in (h_name, a_name, h_score, a_score):
        return None
    if h_score < 0 or a_score < 0:  # -1 = jogo nao disputado
        return None
    start = game.get("startTime", "")
    return GameResult(
        date=start[:10] if isinstance(start, str) and len(start) >= 10 else None,
        home_team=h_name,
        away_team=a_name,
        home_score=int(h_score),
        away_score=int(a_score),
        competition=game.get("competitionDisplayName"),
    )


class Scores365Scraper(BaseScraper):
    source_name = "365scores"

    def search_team(self, name: str) -> Optional[tuple[int, str]]:
        resp = http_get(f"{BASE}/search/?{COMMON}&query={name}&filter=all")
        if resp is None:
            return None
        try:
            competitors = resp.json().get("competitors", [])
        except ValueError:
            logger.warning("365scores: resposta de busca nao-JSON para %r", name)
            return None
        for c in competitors:
            if c.get("sportId") == 1:  # futebol
                return c.get("id"), c.get("name", name)
        return None

    def _fetch_results(self, team_id: int) -> list[GameResult]:
        resp = http_get(f"{BASE}/games/results/?{COMMON}&competitors={team_id}")
        if resp is None:
            return []
        try:
            raw_games = resp.json().get("games", [])
        except ValueError:
            return []
        games = [g for g in (_parse_game(rg) for rg in raw_games) if g]
        games.sort(key=lambda g: g.date or "", reverse=True)
        return games

    def fetch_team_data(self, team_name: str) -> Optional[TeamData]:
        found = self.search_team(team_name)
        if not found:
            logger.warning("365scores: time %r nao encontrado", team_name)
            return None
        team_id, canonical = found
        time.sleep(0.5)

        all_games = self._fetch_results(team_id)
        games = all_games[: config.RECENT_GAMES_LIMIT]
        if not games:
            logger.warning("365scores: nenhum jogo extraido para %r", team_name)
            return None

        team = TeamData(name=canonical, resolved_id=str(team_id), recent_games=games)
        team.goal_stats = stats_calc.compute_goal_stats(games, canonical)
        team.home_record = stats_calc.compute_record(games, canonical, home=True)
        team.away_record = stats_calc.compute_record(games, canonical, home=False)
        team.current_streak = stats_calc.compute_streak(games, canonical)
        # guarda o historico completo para derivar H2H sem novo request
        self._full_history = {canonical.lower(): all_games}
        return team

    def fetch_h2h(self, home: TeamData, away: TeamData) -> list[GameResult]:
        away_lower = away.name.lower()
        # usa o historico completo (ate ~40 jogos) se este scraper coletou o time
        history = getattr(self, "_full_history", {}).get(home.name.lower())
        if history is None and home.resolved_id:
            history = self._fetch_results(int(home.resolved_id))
        if history is None:
            history = home.recent_games
        mutual = [
            g for g in history
            if away_lower in (g.home_team.lower(), g.away_team.lower())
        ]
        return mutual[: config.H2H_LIMIT]
