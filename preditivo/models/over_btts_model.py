import logging

from tensorflow import keras

logger = logging.getLogger(__name__)

MODEL_PATH = "preditivo/models/saved/over_btts.keras"


def build_over_btts_model(num_features: int) -> keras.Model:
    """FFNN com 2 outputs: [Over 2.5, BTTS] via sigmoid.

    Input: vetor de features (~46)
    Output: tensor (N, 2) — coluna 0 = P(Over 2.5), coluna 1 = P(BTTS)
    """
    inputs = keras.Input(shape=(num_features,), name="features")

    x = keras.layers.Dense(64, activation="relu")(inputs)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Dropout(0.3)(x)

    x = keras.layers.Dense(32, activation="relu")(x)
    x = keras.layers.Dropout(0.2)(x)

    outputs = keras.layers.Dense(2, activation="sigmoid", name="over_btts")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="over_btts_model")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    logger.info("Over/BTTS model: %d params", model.count_params())
    return model
