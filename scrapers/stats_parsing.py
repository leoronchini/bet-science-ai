"""Parsing compartilhado do payload /event/{id}/statistics.

Usado pelo SofascoreScraper e pelo SportAPI7Client (mesmo formato de resposta).
Nomes de estatisticas casados por igualdade exata para nao confundir
"Big chances" com "Big chances missed".
"""

import re
from typing import Optional

from models.match_data import MatchStats

# nome do item -> (prefixo do campo em MatchStats, conversor)
_MAPA = {
    "Corner kicks": ("escanteios", int),
    "Yellow cards": ("cartoes_amarelos", int),
    "Red cards": ("cartoes_vermelhos", int),
    "Ball possession": ("posse", float),
    "Shots on target": ("chutes_gol", int),
    "Fouls": ("faltas", int),
    "Offsides": ("impedimentos", int),
    "Expected goals": ("xg", float),
    "Big chances": ("big_chances", int),
    "Accurate passes": ("passes_certos", int),
}


def _numero(valor) -> Optional[float]:
    """Extrai o primeiro numero de valores como '7', '61%', '512 (91%)'."""
    if valor is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(valor))
    return float(m.group()) if m else None


def parse_statistics_payload(data: dict) -> Optional[MatchStats]:
    groups = []
    for period in data.get("statistics", []):
        if period.get("period") == "ALL":
            groups = period.get("groups", [])
            break

    stats = MatchStats()
    for group in groups:
        for item in group.get("statisticsItems", []):
            mapeado = _MAPA.get(item.get("name", ""))
            if not mapeado:
                continue
            prefixo, conv = mapeado
            casa, fora = _numero(item.get("home")), _numero(item.get("away"))
            setattr(stats, f"{prefixo}_casa", conv(casa) if casa is not None else None)
            setattr(stats, f"{prefixo}_fora", conv(fora) if fora is not None else None)

    has_data = any([
        stats.escanteios_casa, stats.cartoes_amarelos_casa,
        stats.cartoes_vermelhos_casa, stats.posse_casa, stats.xg_casa,
    ])
    return stats if has_data else None
