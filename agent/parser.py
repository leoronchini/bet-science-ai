"""Parse do input do usuario: 'Time A vs Time B' -> ParsedMatch."""

import re
from dataclasses import dataclass


@dataclass
class ParsedMatch:
    home_team: str
    away_team: str


class ParseError(Exception):
    pass


# Separadores exigem espacos ao redor para nao quebrar nomes como "Atletico-MG"
_SEPARATOR_RE = re.compile(r"\s+(?:vs\.?|v|x|contra|-)\s+", flags=re.IGNORECASE)


def parse_match_input(raw: str) -> ParsedMatch:
    normalized = re.sub(r"\s+", " ", (raw or "").replace("﻿", "").strip())
    if not normalized:
        raise ParseError("Entrada vazia.")

    parts = _SEPARATOR_RE.split(normalized)
    if len(parts) != 2:
        raise ParseError('Entrada invalida. Use o formato: "Time A vs Time B"')

    home, away = (p.strip() for p in parts)
    if len(home) < 2 or len(away) < 2:
        raise ParseError('Entrada invalida. Use o formato: "Time A vs Time B"')

    return ParsedMatch(home_team=home, away_team=away)
