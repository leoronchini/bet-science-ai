from typing import Optional


TARGET_KEYS = [
    "win_home", "draw", "win_away",
    "gols_casa", "gols_fora", "total_gols",
    "over_25", "btts",
    "escanteios_casa", "escanteios_fora", "total_escanteios",
    "cartoes_casa", "cartoes_fora", "total_cartoes",
]


def calcular_targets(partida: dict) -> Optional[dict[str, float]]:
    """Calcula os rotulos de treino a partir dos dados de uma partida.

    Retorna dict com todas as chaves de TARGET_KEYS.
    Stats indisponiveis (cartoes, escanteios) sao 0.0.
    """
    gols_casa = partida.get("gols_casa")
    gols_fora = partida.get("gols_fora")
    if gols_casa is None or gols_fora is None:
        return None

    total_gols = gols_casa + gols_fora

    ec = partida.get("escanteios_casa")
    ef = partida.get("escanteios_fora")
    cc = partida.get("cartoes_amarelos_casa")
    cf = partida.get("cartoes_amarelos_fora")

    ec_val = float(ec) if ec is not None else 0.0
    ef_val = float(ef) if ef is not None else 0.0
    cc_val = float(cc) if cc is not None else 0.0
    cf_val = float(cf) if cf is not None else 0.0

    return {
        "win_home": 1.0 if gols_casa > gols_fora else 0.0,
        "draw": 1.0 if gols_casa == gols_fora else 0.0,
        "win_away": 1.0 if gols_casa < gols_fora else 0.0,
        "gols_casa": float(gols_casa),
        "gols_fora": float(gols_fora),
        "total_gols": float(total_gols),
        "over_25": 1.0 if total_gols >= 3 else 0.0,
        "btts": 1.0 if gols_casa > 0 and gols_fora > 0 else 0.0,
        "escanteios_casa": ec_val,
        "escanteios_fora": ef_val,
        "total_escanteios": ec_val + ef_val,
        "cartoes_casa": cc_val,
        "cartoes_fora": cf_val,
        "total_cartoes": cc_val + cf_val,
    }
