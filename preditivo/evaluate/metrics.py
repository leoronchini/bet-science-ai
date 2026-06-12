from dataclasses import dataclass, field

import numpy as np


@dataclass
class MetricasModelo:
    accuracy: float = 0.0
    brier_score: float = 0.0
    log_loss: float = 0.0
    mae_gols: float = 0.0
    mae_escanteios: float = 0.0
    mae_cartoes: float = 0.0
    acuracia_over_25: float = 0.0
    acuracia_btts: float = 0.0
    n_amostras: int = 0
    matriz_confusao: list = field(default_factory=list)


def calcular_metricas_outcome(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict:
    """y_true: one-hot (N, 3), y_pred: probabilidades (N, 3)."""
    n = len(y_true)
    if n == 0:
        return {"accuracy": 0, "brier": 0, "log_loss": 0, "n": 0}

    classes_true = np.argmax(y_true, axis=1)
    classes_pred = np.argmax(y_pred, axis=1)

    accuracy = np.mean(classes_true == classes_pred)
    brier = np.mean(np.sum((y_pred - y_true) ** 2, axis=1))

    eps = 1e-15
    y_pred_clip = np.clip(y_pred, eps, 1 - eps)
    log_loss = -np.mean(np.sum(y_true * np.log(y_pred_clip), axis=1))

    return {
        "accuracy": round(float(accuracy), 4),
        "brier": round(float(brier), 4),
        "log_loss": round(float(log_loss), 4),
        "n": n,
    }


def calcular_metricas_regressao(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict:
    mae = np.mean(np.abs(y_true - y_pred))
    mse = np.mean((y_true - y_pred) ** 2)
    return {
        "mae": round(float(mae), 4),
        "mse": round(float(mse), 4),
        "n": len(y_true),
    }


def calcular_metricas_binaria(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict:
    y_pred_bin = (y_pred >= 0.5).astype(float)
    accuracy = np.mean(y_true == y_pred_bin)
    eps = 1e-15
    y_pred_clip = np.clip(y_pred, eps, 1 - eps)
    log_loss = -np.mean(y_true * np.log(y_pred_clip) + (1 - y_true) * np.log(1 - y_pred_clip))
    return {
        "accuracy": round(float(accuracy), 4),
        "log_loss": round(float(log_loss), 4),
        "n": len(y_true),
    }
