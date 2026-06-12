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

    # implementados na proxima task
    def fetch_team_data(self, team_name: str) -> Optional[TeamData]:
        raise NotImplementedError

    def fetch_h2h(self, home: TeamData, away: TeamData) -> list[GameResult]:
        raise NotImplementedError
