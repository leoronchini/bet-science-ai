import logging

from tensorflow import keras

logger = logging.getLogger(__name__)

MODEL_PATH = "preditivo/models/saved/outcome.keras"


def build_outcome_model(num_features: int) -> keras.Model:
    """FFNN para predicao de resultado da partida (V/E/D).

    Input: vetor de ~46 features
    Output: [P(casa), P(empate), P(fora)] via softmax
    """
    inputs = keras.Input(shape=(num_features,), name="features")

    x = keras.layers.Dense(128, activation="relu")(inputs)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Dropout(0.3)(x)

    x = keras.layers.Dense(64, activation="relu")(x)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Dropout(0.2)(x)

    x = keras.layers.Dense(32, activation="relu")(x)
    x = keras.layers.Dropout(0.1)(x)

    outputs = keras.layers.Dense(3, activation="softmax", name="outcome")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="outcome_model")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss="categorical_crossentropy",
        metrics=["accuracy", keras.metrics.BrierScore(name="brier")],
    )
    logger.info("Outcome model: %d params", model.count_params())
    return model
