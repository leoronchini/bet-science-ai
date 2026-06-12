import logging

from tensorflow import keras

logger = logging.getLogger(__name__)

MODEL_PATH = "preditivo/models/saved/score_lstm.keras"
SEQ_LEN = 10
NUM_FEATURES_PER_GAME = 5


def build_score_lstm_model() -> keras.Model:
    """LSTM bidirecional para prever lambdas (gols esperados) de cada time.

    Input: sequencia de 10 jogos por time, 5 features cada:
           [gols_marcados, gols_sofridos, escanteios, cartoes, mandante?]
    Output: [lambda_casa, lambda_fora] via softplus
    """
    casa_input = keras.Input(
        shape=(SEQ_LEN, NUM_FEATURES_PER_GAME), name="seq_casa"
    )
    fora_input = keras.Input(
        shape=(SEQ_LEN, NUM_FEATURES_PER_GAME), name="seq_fora"
    )

    shared_lstm = keras.layers.Bidirectional(
        keras.layers.LSTM(64, return_sequences=False)
    )

    casa_encoded = shared_lstm(casa_input)
    fora_encoded = shared_lstm(fora_input)

    concat = keras.layers.Concatenate()([casa_encoded, fora_encoded])
    x = keras.layers.Dense(32, activation="relu")(concat)
    x = keras.layers.Dropout(0.2)(x)

    lambda_casa = keras.layers.Dense(1, activation="softplus", name="lambda_casa")(x)
    lambda_fora = keras.layers.Dense(1, activation="softplus", name="lambda_fora")(x)

    model = keras.Model(
        inputs={"seq_casa": casa_input, "seq_fora": fora_input},
        outputs={"lambda_casa": lambda_casa, "lambda_fora": lambda_fora},
        name="score_lstm",
    )

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss={"lambda_casa": "mse", "lambda_fora": "mse"},
        metrics={"lambda_casa": "mae", "lambda_fora": "mae"},
    )
    logger.info("Score LSTM model: %d params", model.count_params())
    return model
