"""Infra comum a todos os scrapers: HTTP resiliente e classe base."""

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

import requests

import config
from models.match_data import GameResult, TeamData

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503, 504}


def http_get(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: int = config.HTTP_TIMEOUT,
) -> Optional[requests.Response]:
    """GET com User-Agent padrao, 1 retry com backoff em 429/5xx.

    Retorna None em qualquer falha (logando WARNING). Nunca propaga excecao.
    """
    final_headers = {"User-Agent": config.USER_AGENT}
    if headers:
        final_headers.update(headers)

    for attempt in (1, 2):
        try:
            resp = requests.get(url, headers=final_headers, timeout=timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code in _RETRY_STATUSES and attempt == 1:
                logger.warning("HTTP %s em %s — retry em 2s", resp.status_code, url)
                time.sleep(2)
                continue
            logger.warning("HTTP %s em %s", resp.status_code, url)
            return None
        except requests.RequestException as exc:
            if attempt == 1:
                logger.warning("Falha de rede em %s (%s) — retry em 2s", url, exc)
                time.sleep(2)
                continue
            logger.warning("Falha de rede em %s: %s", url, exc)
            return None
    return None


class BaseScraper(ABC):
    source_name: str = "base"

    @abstractmethod
    def fetch_team_data(self, team_name: str) -> Optional[TeamData]:
        ...

    @abstractmethod
    def fetch_h2h(self, home: TeamData, away: TeamData) -> list[GameResult]:
        ...
