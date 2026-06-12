"""Scraper Understat — xG real, somente top 5 ligas europeias (RN-14).

O site embute JSON em <script>: var datesData = JSON.parse('...escapes \\xNN...').
"""

import json
import logging
import re
from datetime import date
from typing import Optional

import config
from scrapers.base import http_get

logger = logging.getLogger(__name__)

_DATES_DATA_RE = re.compile(r"var\s+datesData\s*=\s*JSON\.parse\('(.+?)'\)", re.DOTALL)

# Aliases para nomes que nao mapeiam direto para o slug do Understat
_TEAM_ALIASES = {
    "manchester united": "Manchester_United",
    "manchester city": "Manchester_City",
    "psg": "Paris_Saint_Germain",
    "paris saint-germain": "Paris_Saint_Germain",
    "inter": "Inter",
    "internazionale": "Inter",
    "atletico madrid": "Atletico_Madrid",
    "atlético madrid": "Atletico_Madrid",
}


def _season_year(today: Optional[date] = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def _slug(team_name: str) -> str:
    alias = _TEAM_ALIASES.get(team_name.lower())
    return alias if alias else team_name.strip().replace(" ", "_")


def fetch_xg(team_name: str) -> Optional[tuple[float, float]]:
    """Retorna (xg_for, xg_against) medios dos ultimos 10 jogos, ou None."""
    url = f"https://understat.com/team/{_slug(team_name)}/{_season_year()}"
    resp = http_get(url)
    if resp is None:
        return None

    match = _DATES_DATA_RE.search(resp.text)
    if not match:
        logger.warning("Understat: datesData nao encontrado para %r", team_name)
        return None

    try:
        decoded = bytes(match.group(1), "utf-8").decode("unicode_escape")
        games = json.loads(decoded)
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("Understat: falha ao decodificar JSON (%s)", exc)
        return None

    played = [g for g in games if g.get("isResult")]
    played.sort(key=lambda g: g.get("datetime", ""), reverse=True)
    played = played[: config.RECENT_GAMES_LIMIT]
    if not played:
        return None

    slug_lower = _slug(team_name).lower()
    xg_for_total = xg_against_total = 0.0
    for g in played:
        side = "h" if g.get("h", {}).get("title", "").replace(" ", "_").lower() == slug_lower else "a"
        other = "a" if side == "h" else "h"
        try:
            xg_for_total += float(g.get("xG", {}).get(side, 0))
            xg_against_total += float(g.get("xG", {}).get(other, 0))
        except (TypeError, ValueError):
            continue
    n = len(played)
    return round(xg_for_total / n, 2), round(xg_against_total / n, 2)
