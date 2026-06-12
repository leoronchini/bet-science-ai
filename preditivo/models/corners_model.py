import logging

from tensorflow import keras

logger = logging.getLogger(__name__)

MODEL_PATH = "preditivo/models/saved/corners.keras"


def build_corners_model(num_features: int) -> keras.Model:
    """FFNN para prever escanteios na partida.

    Input: vetor de features (~46)
    Output: [total_escanteios, escanteios_casa, escanteios_fora] via softplus
    """
    inputs = keras.Input(shape=(num_features,), name="features")

    x = keras.layers.Dense(64, activation="relu")(inputs)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Dropout(0.3)(x)

    x = keras.layers.Dense(32, activation="relu")(x)
    x = keras.layers.Dropout(0.2)(x)

    outputs = keras.layers.Dense(3, activation="softplus", name="corners")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="corners_model")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss="mse",
        metrics=["mae"],
    )
    logger.info("Corners model: %d params", model.count_params())
    return model
