import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
from tensorflow import keras

from models.match_data import MatchData
from preditivo.features.engine import extrair_features_matchdata

logger = logging.getLogger(__name__)

MODELS_DIR = "preditivo/models/saved"


@dataclass
class NNPrediction:
    win_home_pct: float
    draw_pct: float
    win_away_pct: float
    xg_home: float
    xg_away: float
    over_25_pct: float
    btts_pct: float
    total_cards: float
    cards_home: float
    cards_away: float
    total_corners: float
    corners_home: float
    corners_away: float


class PredictorNN:
    """Carrega modelos treinados e faz inferencia."""

    def __init__(self) -> None:
        self._outcome: Optional[keras.Model] = None
        self._corners: Optional[keras.Model] = None
        self._cards: Optional[keras.Model] = None
        self._over_btts: Optional[keras.Model] = None

    def carregar_modelos(self) -> None:
        path_outcome = os.path.join(MODELS_DIR, "outcome.keras")
        if os.path.exists(path_outcome):
            self._outcome = keras.models.load_model(path_outcome)
            logger.info("Outcome model carregado")

        path_corners = os.path.join(MODELS_DIR, "corners.keras")
        if os.path.exists(path_corners):
            self._corners = keras.models.load_model(path_corners)
            logger.info("Corners model carregado")

        path_cards = os.path.join(MODELS_DIR, "cards.keras")
        if os.path.exists(path_cards):
            self._cards = keras.models.load_model(path_cards)
            logger.info("Cards model carregado")

        path_over_btts = os.path.join(MODELS_DIR, "over_btts.keras")
        if os.path.exists(path_over_btts):
            self._over_btts = keras.models.load_model(path_over_btts)
            logger.info("Over/BTTS model carregado")

    @property
    def disponivel(self) -> bool:
        return self._outcome is not None

    def predict(self, match: MatchData) -> Optional[NNPrediction]:
        if not self.disponivel:
            return None

        features = extrair_features_matchdata(match)
        X = np.expand_dims(features, axis=0)

        # Outcome
        if self._outcome:
            out = self._outcome.predict(X, verbose=0)[0]
            win_home = float(out[0]) * 100
            draw = float(out[1]) * 100
            win_away = float(out[2]) * 100
            total = win_home + draw + win_away
            win_home = round(win_home / total * 100, 1)
            draw = round(draw / total * 100, 1)
            win_away = round(100.0 - win_home - draw, 1)
        else:
            win_home = draw = win_away = 33.3

        # Over/BTTS (modelo tem 2 outputs: [over_25, btts])
        over_25 = None
        btts = None
        if self._over_btts:
            ob = self._over_btts.predict(X, verbose=0)
            over_25 = round(float(ob[0][0]) * 100, 1)
            btts = round(float(ob[0][1]) * 100, 1)

        # Cards
        total_cards = cards_home = cards_away = 0.0
        if self._cards:
            c = self._cards.predict(X, verbose=0)[0]
            total_cards = round(float(c[0]), 1)
            cards_home = round(float(c[1]), 1)
            cards_away = round(float(c[2]), 1)

        # Corners
        total_corners = corners_home = corners_away = 0.0
        if self._corners:
            c = self._corners.predict(X, verbose=0)[0]
            total_corners = round(float(c[0]), 1)
            corners_home = round(float(c[1]), 1)
            corners_away = round(float(c[2]), 1)

        # xG aproximado via Poisson inverso
        # (usamos os lambdas do Poisson existente no predictor.py)
        xg_home = round(
            (match.home_team.goal_stats.avg_scored or 1.3)
            + (match.away_team.goal_stats.avg_conceded or 1.3), 2
        ) / 2
        xg_away = round(
            (match.away_team.goal_stats.avg_scored or 1.3)
            + (match.home_team.goal_stats.avg_conceded or 1.3), 2
        ) / 2

        return NNPrediction(
            win_home_pct=win_home,
            draw_pct=draw,
            win_away_pct=win_away,
            xg_home=xg_home,
            xg_away=xg_away,
            over_25_pct=over_25 or 50.0,
            btts_pct=btts or 50.0,
            total_cards=total_cards,
            cards_home=cards_home,
            cards_away=cards_away,
            total_corners=total_corners,
            corners_home=corners_home,
            corners_away=corners_away,
        )
