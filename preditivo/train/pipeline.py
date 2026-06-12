import logging

import numpy as np
import tensorflow as tf

from preditivo.data.database import init_db
from preditivo.data.loader import carregar_dataset
from preditivo.features.targets import TARGET_KEYS
from preditivo.models.cards_model import build_cards_model, MODEL_PATH as CARDS_PATH
from preditivo.models.corners_model import build_corners_model, MODEL_PATH as CORNERS_PATH
from preditivo.models.outcome_model import build_outcome_model, MODEL_PATH as OUTCOME_PATH
from preditivo.models.over_btts_model import build_over_btts_model, MODEL_PATH as OVER_BTTS_PATH

logger = logging.getLogger(__name__)

SAVED_DIR = "preditivo/models/saved"


def _mapear_y(
    ds: tf.data.Dataset,
    cols: list[str],
    num_out: int,
) -> tf.data.Dataset:
    """Mapeia um dataset (X, y_dict) para (X, y_array)."""
    def _map(X, y_dict):
        y_out = tf.stack([y_dict[k] for k in cols], axis=-1)
        if num_out == 1:
            y_out = tf.reshape(y_out, (-1, 1))
        return X, y_out
    return ds.map(_map)


def treinar_todos(
    epochs: int = 100,
    batch_size: int = 32,
) -> dict[str, float]:
    """Treina todos os modelos sequencialmente."""
    init_db()

    train_ds, val_ds, num_features = carregar_dataset(
        batch_size=batch_size,
    )

    if num_features == 0:
        logger.warning("Sem dados para treinar. Execute coleta primeiro.")
        return {"erro": 0.0}

    resultados = {}

    # Outcome: win_home, draw, win_away
    logger.info("=== Treinando Outcome Model ===")
    ds_train_out = _mapear_y(train_ds, ["win_home", "draw", "win_away"], 3)
    ds_val_out = _mapear_y(val_ds, ["win_home", "draw", "win_away"], 3)
    model = build_outcome_model(num_features)
    history = model.fit(
        ds_train_out, validation_data=ds_val_out,
        epochs=epochs,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=10, restore_best_weights=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6,
            ),
        ],
        verbose=1,
    )
    import os
    os.makedirs(os.path.dirname(OUTCOME_PATH), exist_ok=True)
    model.save(OUTCOME_PATH)
    resultados["outcome"] = min(history.history["val_loss"])
    logger.info("Outcome salvo: val_loss=%.4f", resultados["outcome"])

    # Cards: total_cartoes, cartoes_casa, cartoes_fora
    logger.info("=== Treinando Cards Model ===")
    ds_train_cards = _mapear_y(train_ds, ["total_cartoes", "cartoes_casa", "cartoes_fora"], 3)
    ds_val_cards = _mapear_y(val_ds, ["total_cartoes", "cartoes_casa", "cartoes_fora"], 3)
    model = build_cards_model(num_features)
    history = model.fit(
        ds_train_cards, validation_data=ds_val_cards,
        epochs=epochs,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=10, restore_best_weights=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6,
            ),
        ],
        verbose=1,
    )
    os.makedirs(os.path.dirname(CARDS_PATH), exist_ok=True)
    model.save(CARDS_PATH)
    resultados["cards"] = min(history.history["val_loss"])
    logger.info("Cards salvo: val_loss=%.4f", resultados["cards"])

    # Corners: total_escanteios, escanteios_casa, escanteios_fora
    logger.info("=== Treinando Corners Model ===")
    ds_train_corners = _mapear_y(train_ds, ["total_escanteios", "escanteios_casa", "escanteios_fora"], 3)
    ds_val_corners = _mapear_y(val_ds, ["total_escanteios", "escanteios_casa", "escanteios_fora"], 3)
    model = build_corners_model(num_features)
    history = model.fit(
        ds_train_corners, validation_data=ds_val_corners,
        epochs=epochs,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=10, restore_best_weights=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6,
            ),
        ],
        verbose=1,
    )
    os.makedirs(os.path.dirname(CORNERS_PATH), exist_ok=True)
    model.save(CORNERS_PATH)
    resultados["corners"] = min(history.history["val_loss"])
    logger.info("Corners salvo: val_loss=%.4f", resultados["corners"])

    # Over/BTTS: over_25, btts
    logger.info("=== Treinando Over/BTTS Model ===")
    ds_train_ob = _mapear_y(train_ds, ["over_25", "btts"], 2)
    ds_val_ob = _mapear_y(val_ds, ["over_25", "btts"], 2)
    model = build_over_btts_model(num_features)
    history = model.fit(
        ds_train_ob, validation_data=ds_val_ob,
        epochs=epochs,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=10, restore_best_weights=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6,
            ),
        ],
        verbose=1,
    )
    os.makedirs(os.path.dirname(OVER_BTTS_PATH), exist_ok=True)
    model.save(OVER_BTTS_PATH)
    resultados["over_btts"] = min(history.history["val_loss"])
    logger.info("Over/BTTS salvo: val_loss=%.4f", resultados["over_btts"])

    logger.info("Treinamento concluido: %s", resultados)
    return resultados
