import logging

import numpy as np
import tensorflow as tf

from preditivo.data.database import buscar_todas_partidas
from preditivo.features.engine import extrair_features
from preditivo.features.targets import TARGET_KEYS, calcular_targets

logger = logging.getLogger(__name__)

BATCH_SIZE = 32
VAL_SPLIT = 0.15


def carregar_dataset(
    batch_size: int = BATCH_SIZE,
    val_split: float = VAL_SPLIT,
) -> tuple[tf.data.Dataset, tf.data.Dataset, int]:
    """Carrega dados do banco e retorna datasets de treino e validacao.

    Returns:
        (train_ds, val_ds, num_features)
    """
    partidas = buscar_todas_partidas()
    if not partidas:
        logger.warning("Nenhuma partida encontrada no banco")
        return tf.data.Dataset.from_tensor_slices([]), tf.data.Dataset.from_tensor_slices([]), 0

    X_list, y_list = [], []
    for p in partidas:
        feats = extrair_features(p)
        if feats is None:
            continue
        targets = calcular_targets(p)
        if targets is None:
            continue
        X_list.append(feats)
        y_list.append(targets)

    if not X_list:
        return tf.data.Dataset.from_tensor_slices([]), tf.data.Dataset.from_tensor_slices([]), 0

    X = np.array(X_list, dtype=np.float32)
    y = {k: np.array([d[k] for d in y_list], dtype=np.float32) for k in TARGET_KEYS}

    n = len(X)
    n_val = max(1, int(n * val_split))
    indices = np.random.permutation(n)
    val_idx = indices[:n_val]
    train_idx = indices[n_val:]

    X_train, X_val = X[train_idx], X[val_idx]
    y_train = {k: v[train_idx] for k, v in y.items()}
    y_val = {k: v[val_idx] for k, v in y.items()}

    train_ds = tf.data.Dataset.from_tensor_slices((X_train, y_train))
    train_ds = train_ds.shuffle(1024).batch(batch_size).prefetch(tf.data.AUTOTUNE)

    val_ds = tf.data.Dataset.from_tensor_slices((X_val, y_val))
    val_ds = val_ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)

    num_features = X.shape[1]
    logger.info(
        "Dataset: %d amostras (%d treino, %d val), %d features",
        n, n - n_val, n_val, num_features,
    )
    return train_ds, val_ds, num_features
