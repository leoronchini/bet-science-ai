import logging

import numpy as np

from preditivo.data.database import buscar_todas_partidas
from preditivo.features.engine import extrair_features
from preditivo.features.targets import calcular_targets
from preditivo.evaluate.metrics import (
    calcular_metricas_binaria,
    calcular_metricas_outcome,
    calcular_metricas_regressao,
)
from tensorflow import keras

logger = logging.getLogger(__name__)

MODELS_DIR = "preditivo/models/saved"


def backtest_outcome() -> dict:
    """Avalia o modelo de outcome contra todo o historico."""
    path = f"{MODELS_DIR}/outcome.keras"
    try:
        model = keras.models.load_model(path)
    except (OSError, ValueError) as exc:
        logger.warning("Modelo outcome nao encontrado: %s", exc)
        return {"erro": "modelo nao encontrado"}

    partidas = buscar_todas_partidas()
    X, y_outcome = [], []
    for p in partidas:
        feats = extrair_features(p)
        if feats is None:
            continue
        targets = calcular_targets(p)
        if targets is None:
            continue
        X.append(feats)
        gols_casa = p["gols_casa"]
        gols_fora = p["gols_fora"]
        if gols_casa > gols_fora:
            y_outcome.append([1.0, 0.0, 0.0])
        elif gols_casa == gols_fora:
            y_outcome.append([0.0, 1.0, 0.0])
        else:
            y_outcome.append([0.0, 0.0, 1.0])

    if not X:
        return {"erro": "sem dados"}

    X = np.array(X, dtype=np.float32)
    y_true = np.array(y_outcome, dtype=np.float32)
    y_pred = model.predict(X, verbose=0)

    return calcular_metricas_outcome(y_true, y_pred)


def backtest_over_btts() -> dict:
    """Avalia modelo de Over/BTTS."""
    path = f"{MODELS_DIR}/over_btts.keras"
    try:
        model = keras.models.load_model(path)
    except (OSError, ValueError) as exc:
        logger.warning("Modelo over/btts nao encontrado: %s", exc)
        return {"erro": "modelo nao encontrado"}

    partidas = buscar_todas_partidas()
    X, y_over, y_btts = [], [], []
    for p in partidas:
        feats = extrair_features(p)
        if feats is None:
            continue
        gols_casa = p["gols_casa"]
        gols_fora = p["gols_fora"]
        if gols_casa is None or gols_fora is None:
            continue
        X.append(feats)
        y_over.append(1.0 if gols_casa + gols_fora >= 3 else 0.0)
        y_btts.append(1.0 if gols_casa > 0 and gols_fora > 0 else 0.0)

    if not X:
        return {"erro": "sem dados"}

    X = np.array(X, dtype=np.float32)
    preds = model.predict(X, verbose=0)

    return {
        "over_25": calcular_metricas_binaria(
            np.array(y_over), preds[:, 0]
        ),
        "btts": calcular_metricas_binaria(
            np.array(y_btts), preds[:, 1]
        ),
    }
