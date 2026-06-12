import logging
from typing import Optional

import numpy as np

from models.match_data import MatchData

logger = logging.getLogger(__name__)

NUM_FEATURES = 46


def extrair_features(partida: dict) -> Optional[np.ndarray]:
    """Transforma uma linha do banco em vetor numerico para treino.

    Returns:
        np.ndarray shape (NUM_FEATURES,) ou None se dados insuficientes.
    """
    gols_casa = partida.get("gols_casa")
    gols_fora = partida.get("gols_fora")
    if gols_casa is None or gols_fora is None:
        return None

    feats = np.zeros(NUM_FEATURES, dtype=np.float32)
    idx = 0

    # [0-1] Gols da partida (normalizados)
    feats[idx] = min(gols_casa / 6.0, 1.0)
    idx += 1
    feats[idx] = min(gols_fora / 6.0, 1.0)
    idx += 1

    # [2-3] Total de gols e diferenca
    total = gols_casa + gols_fora
    feats[idx] = min(total / 8.0, 1.0)
    idx += 1
    feats[idx] = min(abs(gols_casa - gols_fora) / 5.0, 1.0)
    idx += 1

    # [4-5] Escanteios (normalizados 0-20)
    ec = _norm(partida.get("escanteios_casa"), 20.0)
    ef = _norm(partida.get("escanteios_fora"), 20.0)
    feats[idx] = ec
    idx += 1
    feats[idx] = ef
    idx += 1
    feats[idx] = _norm(partida.get("total_escanteios"), 30.0) if ec >= 0 and ef >= 0 else -1.0
    idx += 1

    # [7-8] Cartoes amarelos (normalizados 0-10)
    cc = _norm(partida.get("cartoes_amarelos_casa"), 8.0)
    cf = _norm(partida.get("cartoes_amarelos_fora"), 8.0)
    feats[idx] = cc
    idx += 1
    feats[idx] = cf
    idx += 1
    feats[idx] = _norm(partida.get("total_cartoes"), 15.0) if cc >= 0 and cf >= 0 else -1.0
    idx += 1

    # [10-11] Cartoes vermelhos (normalizados 0-3)
    feats[idx] = _norm(partida.get("cartoes_vermelhos_casa"), 3.0)
    idx += 1
    feats[idx] = _norm(partida.get("cartoes_vermelhos_fora"), 3.0)
    idx += 1

    # [12-13] Posse (0-100%)
    feats[idx] = _norm(partida.get("posse_casa"), 100.0)
    idx += 1
    feats[idx] = _norm(partida.get("posse_fora"), 100.0)
    idx += 1

    # [14-15] Chutes no gol (normalizados 0-15)
    feats[idx] = _norm(partida.get("chutes_gol_casa"), 15.0)
    idx += 1
    feats[idx] = _norm(partida.get("chutes_gol_fora"), 15.0)
    idx += 1

    # [16-17] Faltas (normalizados 0-25)
    feats[idx] = _norm(partida.get("faltas_casa"), 25.0)
    idx += 1
    feats[idx] = _norm(partida.get("faltas_fora"), 25.0)
    idx += 1

    # [18] Resultado (one-hot: V=0, E=0.5, D=1)
    if gols_casa > gols_fora:
        feats[idx] = 0.0
    elif gols_casa == gols_fora:
        feats[idx] = 0.5
    else:
        feats[idx] = 1.0
    idx += 1

    # [19-20] Indicadores binarios
    feats[idx] = 1.0 if gols_casa > 0 and gols_fora > 0 else 0.0
    idx += 1
    feats[idx] = 1.0 if total >= 3 else 0.0
    idx += 1

    # [21-24] Diferenca entre times (casa - fora)
    feats[idx] = gols_casa - gols_fora
    idx += 1
    feats[idx] = ec - ef if ec >= 0 and ef >= 0 else 0.0
    idx += 1
    feats[idx] = cc - cf if cc >= 0 and cf >= 0 else 0.0
    idx += 1
    feats[idx] = _norm(partida.get("posse_casa", 50), 100.0) - _norm(partida.get("posse_fora", 50), 100.0)
    idx += 1

    # [25-45] Espaco reserva para features futuras
    # (embedding de time, features temporais, etc.)

    return feats


def extrair_features_matchdata(match: MatchData) -> np.ndarray:
    """Transforma MatchData (da consulta em tempo real) em vetor numerico.

    Usado na inferencia (nao no treino).
    """
    feats = np.zeros(NUM_FEATURES, dtype=np.float32)
    idx = 0

    home = match.home_team
    away = match.away_team
    h_gs = home.goal_stats
    a_gs = away.goal_stats

    # [0-1] Medias de gols dos times (normalizados 0-4)
    feats[idx] = _norm(h_gs.avg_scored, 4.0)
    idx += 1
    feats[idx] = _norm(a_gs.avg_scored, 4.0)
    idx += 1

    # [2-3] Medias de gols sofridos
    feats[idx] = _norm(h_gs.avg_conceded, 4.0)
    idx += 1
    feats[idx] = _norm(a_gs.avg_conceded, 4.0)
    idx += 1

    # [4-7] Forca ofensiva/defensiva relativa
    feats[idx] = _norm(h_gs.avg_scored, 4.0) - _norm(a_gs.avg_conceded, 4.0)
    idx += 1
    feats[idx] = _norm(a_gs.avg_scored, 4.0) - _norm(h_gs.avg_conceded, 4.0)
    idx += 1
    feats[idx] = _norm(h_gs.avg_scored, 4.0) + _norm(a_gs.avg_conceded, 4.0)
    idx += 1
    feats[idx] = _norm(a_gs.avg_scored, 4.0) + _norm(h_gs.avg_conceded, 4.0)
    idx += 1

    # [8-13] BTTS e overs
    feats[idx] = _norm(h_gs.btts_pct, 100.0)
    idx += 1
    feats[idx] = _norm(a_gs.btts_pct, 100.0)
    idx += 1
    feats[idx] = _norm(h_gs.over_25_pct, 100.0)
    idx += 1
    feats[idx] = _norm(a_gs.over_25_pct, 100.0)
    idx += 1
    feats[idx] = _norm(h_gs.over_35_pct, 100.0)
    idx += 1
    feats[idx] = _norm(a_gs.over_35_pct, 100.0)
    idx += 1

    # [14-15] Clean sheets
    feats[idx] = _norm(h_gs.clean_sheets_pct, 100.0)
    idx += 1
    feats[idx] = _norm(a_gs.clean_sheets_pct, 100.0)
    idx += 1

    # [16-17] xG
    feats[idx] = _norm(home.xg_for, 3.0)
    idx += 1
    feats[idx] = _norm(away.xg_for, 3.0)
    idx += 1
    feats[idx] = _norm(home.xg_against, 3.0)
    idx += 1
    feats[idx] = _norm(away.xg_against, 3.0)
    idx += 1

    # [20-21] Forma recente (proporcao de vitorias nos ultimos 10)
    form_h = home.form_string
    form_a = away.form_string
    feats[idx] = form_h.count("V") / max(len(form_h), 1)
    idx += 1
    feats[idx] = form_a.count("V") / max(len(form_a), 1)
    idx += 1

    # [22-23] Empates na forma
    feats[idx] = form_h.count("E") / max(len(form_h), 1)
    idx += 1
    feats[idx] = form_a.count("E") / max(len(form_a), 1)
    idx += 1

    # [24-25] Tamanho do streak (normalizado 0-10)
    streak_h = _streak_size(home.current_streak)
    streak_a = _streak_size(away.current_streak)
    feats[idx] = min(streak_h / 10.0, 1.0)
    idx += 1
    feats[idx] = min(streak_a / 10.0, 1.0)
    idx += 1

    # [26-27] Streak positivo? (vitoria)
    feats[idx] = 1.0 if streak_h > 0 else 0.0
    idx += 1
    feats[idx] = 1.0 if streak_a > 0 else 0.0
    idx += 1

    # [28-30] H2H
    if match.h2h:
        total_h2h = len(match.h2h)
        h2h_wins_home = sum(
            1 for g in match.h2h
            if g.home_team.lower() == home.name.lower() and g.home_score > g.away_score
        )
        h2h_wins_home += sum(
            1 for g in match.h2h
            if g.away_team.lower() == home.name.lower() and g.away_score > g.home_score
        )
        feats[idx] = h2h_wins_home / max(total_h2h, 1)
    idx += 1

    if match.h2h:
        h2h_avg_gols_home = sum(
            g.home_score for g in match.h2h
            if g.home_team.lower() == home.name.lower()
        ) + sum(
            g.away_score for g in match.h2h
            if g.away_team.lower() == home.name.lower()
        )
        feats[idx] = _norm(h2h_avg_gols_home / max(len(match.h2h), 1), 4.0)
    idx += 1

    if match.h2h:
        h2h_avg_gols_away = sum(
            g.away_score for g in match.h2h
            if g.home_team.lower() == away.name.lower()
        ) + sum(
            g.home_score for g in match.h2h
            if g.away_team.lower() == away.name.lower()
        )
        feats[idx] = _norm(h2h_avg_gols_away / max(len(match.h2h), 1), 4.0)
    idx += 1

    # preencher resto com 0 (features futuras)
    return feats


def _norm(val, max_val: float) -> float:
    if val is None:
        return -1.0
    return min(max(float(val) / max_val, 0.0), 1.0)


def _streak_size(streak: Optional[str]) -> int:
    if not streak:
        return 0
    try:
        partes = streak.split()
        return int(partes[0]) if partes else 0
    except (ValueError, IndexError):
        return 0
