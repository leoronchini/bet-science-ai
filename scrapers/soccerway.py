"""Scraper Soccerway — fallback HTML com BeautifulSoup.

Cobre: resultados recentes e H2H derivado. Artilheiros e xG fora do alcance.
"""

import logging
import re
import time
from typing import Optional

from bs4 import BeautifulSoup

import config
from models.match_data import GameResult, TeamData
from scrapers import stats_calc
from scrapers.base import BaseScraper, http_get

logger = logging.getLogger(__name__)

BASE = "https://int.soccerway.com"
_SCORE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")


class SoccerwayScraper(BaseScraper):
    source_name = "soccerway"

    def _find_team_url(self, team_name: str) -> Optional[str]:
        resp = http_get(f"{BASE}/search/?q={team_name}")
        if resp is None:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        link = soup.select_one('a[href*="/teams/"]')
        return BASE + link["href"] if link and link.get("href") else None

    def fetch_team_data(self, team_name: str) -> Optional[TeamData]:
        team_url = self._find_team_url(team_name)
        if not team_url:
            logger.warning("Soccerway: time %r nao encontrado", team_name)
            return None
        time.sleep(0.5)

        resp = http_get(team_url)
        if resp is None:
            return None
        soup = BeautifulSoup(resp.text, "lxml")

        games: list[GameResult] = []
        table = soup.select_one("table.matches")
        if table is None:
            logger.warning("Soccerway: tabela de jogos ausente para %r", team_name)
            return None
        for row in table.select("tr"):
            cells = row.select("td")
            texts = [c.get_text(" ", strip=True) for c in cells]
            if len(texts) < 4:
                continue
            score_idx = next((i for i, t in enumerate(texts) if _SCORE_RE.fullmatch(t)), None)
            if score_idx is None or score_idx == 0 or score_idx >= len(texts) - 1:
                continue
            m = _SCORE_RE.fullmatch(texts[score_idx])
            games.append(
                GameResult(
                    date=None,
                    home_team=texts[score_idx - 1],
                    away_team=texts[score_idx + 1],
                    home_score=int(m.group(1)),
                    away_score=int(m.group(2)),
                )
            )

        games = games[: config.RECENT_GAMES_LIMIT]
        if not games:
            return None

        team = TeamData(name=team_name, recent_games=games)
        team.goal_stats = stats_calc.compute_goal_stats(games, team_name)
        team.home_record = stats_calc.compute_record(games, team_name, home=True)
        team.away_record = stats_calc.compute_record(games, team_name, home=False)
        team.current_streak = stats_calc.compute_streak(games, team_name)
        return team

    def fetch_h2h(self, home: TeamData, away: TeamData) -> list[GameResult]:
        away_lower = away.name.lower()
        mutual = [
            g
            for g in home.recent_games
            if away_lower in (g.home_team.lower(), g.away_team.lower())
        ]
        return mutual[: config.H2H_LIMIT]
