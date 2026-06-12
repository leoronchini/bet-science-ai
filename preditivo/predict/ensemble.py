import logging
from typing import Optional

from models.match_data import Prediction, ScorePrediction
from preditivo.predict.nn_predictor import NNPrediction

logger = logging.getLogger(__name__)

PESO_NN = 0.6


def blend(
    poisson: Prediction,
    nn_pred: Optional[NNPrediction],
    peso_nn: float = PESO_NN,
) -> Prediction:
    """Combina predicao Poisson com NN via media ponderada.

    Retorna um novo Prediction com todos os campos preenchidos.
    """
    if nn_pred is None:
        return poisson

    peso_poisson = 1.0 - peso_nn

    # Outcome blend
    win_home = poisson.win_home_pct * peso_poisson + nn_pred.win_home_pct * peso_nn
    draw = poisson.draw_pct * peso_poisson + nn_pred.draw_pct * peso_nn
    win_away = poisson.win_away_pct * peso_poisson + nn_pred.win_away_pct * peso_nn
    total = win_home + draw + win_away
    win_home = round(win_home / total * 100, 1)
    draw = round(draw / total * 100, 1)
    win_away = round(100.0 - win_home - draw, 1)

    # xG blend
    xg_home = _blend_float(poisson.xg_home, nn_pred.xg_home, peso_poisson, peso_nn)
    xg_away = _blend_float(poisson.xg_away, nn_pred.xg_away, peso_poisson, peso_nn)

    # Over/BTTS blend
    over_25 = _blend_float(poisson.over_25_pct, nn_pred.over_25_pct, peso_poisson, peso_nn)
    btts = _blend_float(poisson.btts_pct, nn_pred.btts_pct, peso_poisson, peso_nn)

    return Prediction(
        xg_home=xg_home,
        xg_away=xg_away,
        win_home_pct=win_home,
        draw_pct=draw,
        win_away_pct=win_away,
        top_scores=poisson.top_scores,
        over_25_pct=over_25,
        btts_pct=btts,
        likely_scorers=poisson.likely_scorers,
        cards_total=nn_pred.total_cards,
        cards_home=nn_pred.cards_home,
        cards_away=nn_pred.cards_away,
        corners_total=nn_pred.total_corners,
        corners_home=nn_pred.corners_home,
        corners_away=nn_pred.corners_away,
    )


def _blend_float(
    a: Optional[float],
    b: Optional[float],
    peso_a: float,
    peso_b: float,
) -> Optional[float]:
    if a is None and b is None:
        return None
    if a is None:
        return round(b, 1)
    if b is None:
        return round(a, 1)
    return round(a * peso_a + b * peso_b, 1)
