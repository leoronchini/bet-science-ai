"""Cliente SportAPI7 (RapidAPI) — fonte primaria de coleta historica.

API comercial sobre os dados do Sofascore: mesmos paths e IDs de
times/eventos do scraper sofascore.py, que permanece como fallback.
Toda resposta 200 e cacheada em disco para nao gastar cota em reprocessos.
"""

import hashlib
import json
import logging
import os
import time
from typing import Optional

import requests

import config
from models.match_data import GameResult, MatchStats, PlayerMatchStats, TeamData
from scrapers import stats_calc
from scrapers.base import BaseScraper
from scrapers.sofascore import _parse_event
from scrapers.stats_parsing import parse_statistics_payload

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join("data", "cache_api")


class QuotaExceededError(RuntimeError):
    """Cota do RapidAPI esgotada ou limite de chamadas da sessao atingido."""


class SportAPI7Client(BaseScraper):
    source_name = "sportapi7"

    def __init__(self, refresh: bool = False, limite_chamadas: Optional[int] = None):
        self.refresh = refresh
        self.limite_chamadas = limite_chamadas
        self.chamadas_api = 0
        self.chamadas_cache = 0

    # ------------------------------------------------------------ HTTP/cache

    def _cache_path(self, path: str) -> str:
        digest = hashlib.sha1(path.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{digest}.json")

    def _get(self, path: str) -> Optional[dict]:
        cache_file = self._cache_path(path)
        if not self.refresh and os.path.exists(cache_file):
            self.chamadas_cache += 1
            with open(cache_file) as f:
                return json.load(f)

        if not config.RAPIDAPI_KEY:
            raise RuntimeError(
                "RAPIDAPI_KEY ausente — configure no .env (veja .env.example)"
            )
        if self.limite_chamadas is not None and self.chamadas_api >= self.limite_chamadas:
            raise QuotaExceededError(
                f"limite de {self.limite_chamadas} chamadas da sessao atingido"
            )

        url = f"https://{config.SPORTAPI7_HOST}/api/v1{path}"
        headers = {
            "x-rapidapi-key": config.RAPIDAPI_KEY,
            "x-rapidapi-host": config.SPORTAPI7_HOST,
        }
        for tentativa in range(config.SPORTAPI7_MAX_RETRIES):
            time.sleep(config.SPORTAPI7_DELAY)
            try:
                resp = requests.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
            except requests.RequestException as exc:
                logger.warning("SportAPI7: falha de rede em %s: %s", path, exc)
                return None
            self.chamadas_api += 1

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    logger.warning("SportAPI7: resposta nao-JSON em %s", path)
                    return None
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(cache_file, "w") as f:
                    json.dump(data, f)
                return data
            if resp.status_code in (401, 403):
                raise RuntimeError(
                    f"SportAPI7 HTTP {resp.status_code}: RAPIDAPI_KEY invalida "
                    "ou sem assinatura ativa — verifique o .env"
                )
            if resp.status_code == 429:
                espera = 2 * (2 ** tentativa)
                logger.warning("SportAPI7: 429 em %s — backoff %ss", path, espera)
                time.sleep(espera)
                continue
            logger.warning("SportAPI7: HTTP %s em %s", resp.status_code, path)
            return None

        raise QuotaExceededError("cota SportAPI7 esgotada (HTTP 429 persistente)")

    # ------------------------------------------------------------- endpoints

    def search_team(self, name: str, national: bool = False) -> Optional[tuple[int, str]]:
        data = self._get(f"/search/all?q={name}")
        if not data:
            return None
        candidatos = []
        for item in data.get("results", []):
            entity = item.get("entity", {})
            if item.get("type") == "team" and entity.get("sport", {}).get("slug") == "football":
                candidatos.append(entity)
        if national:
            nacionais = [e for e in candidatos if e.get("national")]
            candidatos = nacionais or candidatos
        if not candidatos:
            return None
        escolhido = candidatos[0]
        return escolhido.get("id"), escolhido.get("name", name)

    def _last_events(self, team_id: int) -> list[dict]:
        data = self._get(f"/team/{team_id}/events/last/0")
        return data.get("events", []) if data else []

    def eventos_historicos(self, team_id: int, max_paginas: int = 40) -> list[dict]:
        """Pagina /events/last/{p} ate esgotar o historico disponivel."""
        eventos: list[dict] = []
        for pagina in range(max_paginas):
            data = self._get(f"/team/{team_id}/events/last/{pagina}")
            if not data:
                break
            eventos.extend(data.get("events", []))
            if not data.get("hasNextPage"):
                break
        return eventos

    def fetch_event_statistics(self, event_id: int) -> Optional[MatchStats]:
        data = self._get(f"/event/{event_id}/statistics")
        if not data:
            return None
        return parse_statistics_payload(data)

    def fetch_event_lineups(self, event_id: int) -> list[PlayerMatchStats]:
        data = self._get(f"/event/{event_id}/lineups")
        if not data:
            return []
        jogadores = []
        for lado, rotulo in (("home", "casa"), ("away", "fora")):
            for entry in data.get(lado, {}).get("players", []):
                player = entry.get("player", {})
                st = entry.get("statistics") or {}
                jogadores.append(PlayerMatchStats(
                    nome=player.get("name", "?"),
                    sofascore_id=player.get("id"),
                    posicao=player.get("position"),
                    time=rotulo,
                    minutos=st.get("minutesPlayed"),
                    gols=st.get("goals"),
                    assistencias=st.get("goalAssist"),
                    chutes=st.get("onTargetScoringAttempt"),
                    nota=st.get("rating"),
                ))
        return jogadores

    def enrich_events_with_stats(self, events: list[dict]) -> None:
        """Enriquece eventos finalizados com MatchStats in-place (interface sofascore)."""
        for event in events:
            if event.get("status", {}).get("type") != "finished":
                continue
            event_id = event.get("id")
            if not event_id:
                continue
            stats = self.fetch_event_statistics(event_id)
            if stats:
                event["_stats"] = stats

    # ------------------------------------------- interface BaseScraper

    def fetch_team_data(self, team_name: str) -> Optional[TeamData]:
        found = self.search_team(team_name, national=True)
        if not found:
            logger.warning("SportAPI7: time %r nao encontrado", team_name)
            return None
        team_id, canonical = found
        events = self._last_events(team_id)
        finished = [e for e in events if e.get("status", {}).get("type") == "finished"]
        self.enrich_events_with_stats(finished)
        finished.reverse()  # API retorna do mais antigo para o mais recente
        games = [g for g in (_parse_event(e) for e in finished) if g]
        games = games[: config.RECENT_GAMES_LIMIT]

        team = TeamData(name=canonical, resolved_id=str(team_id), recent_games=games)
        team.goal_stats = stats_calc.compute_goal_stats(games, canonical)
        team.home_record = stats_calc.compute_record(games, canonical, home=True)
        team.away_record = stats_calc.compute_record(games, canonical, home=False)
        team.current_streak = stats_calc.compute_streak(games, canonical)
        return team

    def fetch_h2h(self, home: TeamData, away: TeamData) -> list[GameResult]:
        away_lower = away.name.lower()
        mutual = [
            g for g in home.recent_games
            if away_lower in (g.home_team.lower(), g.away_team.lower())
        ]
        return mutual[: config.H2H_LIMIT]
