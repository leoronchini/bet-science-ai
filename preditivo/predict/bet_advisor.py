import logging
from dataclasses import dataclass, field
from typing import Optional

from preditivo.predict.ensemble import EnsemblePrediction

logger = logging.getLogger(__name__)


@dataclass
class BetRecommendation:
    mercado: str
    predicao: str
    probabilidade: float
    odds_minima: float
    ev: Optional[float] = None


@dataclass
class BetAnalysis:
    recomendacoes: list[BetRecommendation] = field(default_factory=list)


def analisar_apostas(
    pred: EnsemblePrediction,
) -> BetAnalysis:
    """Analisa as probabilidades e gera recomendacoes de apostas com EV."""
    analise = BetAnalysis()

    _adicionar_se_valido(
        analise,
        "Vitoria Casa",
        f"{pred.win_home_pct:.1f}%",
        pred.win_home_pct / 100.0,
        1.0 / (pred.win_home_pct / 100.0) * 0.95 if pred.win_home_pct > 0 else 0,
    )
    _adicionar_se_valido(
        analise,
        "Empate",
        f"{pred.draw_pct:.1f}%",
        pred.draw_pct / 100.0,
        1.0 / (pred.draw_pct / 100.0) * 0.95 if pred.draw_pct > 0 else 0,
    )
    _adicionar_se_valido(
        analise,
        "Vitoria Fora",
        f"{pred.win_away_pct:.1f}%",
        pred.win_away_pct / 100.0,
        1.0 / (pred.win_away_pct / 100.0) * 0.95 if pred.win_away_pct > 0 else 0,
    )
    _adicionar_se_valido(
        analise,
        "Over 2.5 Gols",
        f"{pred.over_25_pct:.1f}%",
        (pred.over_25_pct or 50.0) / 100.0,
        1.0 / ((pred.over_25_pct or 50.0) / 100.0) * 0.95 if pred.over_25_pct and pred.over_25_pct > 0 else 0,
    )
    _adicionar_se_valido(
        analise,
        "BTTS",
        f"{pred.btts_pct:.1f}%",
        (pred.btts_pct or 50.0) / 100.0,
        1.0 / ((pred.btts_pct or 50.0) / 100.0) * 0.95 if pred.btts_pct and pred.btts_pct > 0 else 0,
    )

    if pred.total_cards is not None:
        prob_cards_over = min(pred.total_cards / 8.0, 1.0)
        _adicionar_se_valido(
            analise,
            "Over 4.5 Cartoes",
            f"{pred.total_cards:.1f} (media)",
            prob_cards_over,
            1.0 / prob_cards_over * 0.95 if prob_cards_over > 0 else 0,
        )

    if pred.total_corners is not None:
        prob_corners_over = min(pred.total_corners / 12.0, 1.0)
        _adicionar_se_valido(
            analise,
            "Over 9.5 Escanteios",
            f"{pred.total_corners:.1f} (media)",
            prob_corners_over,
            1.0 / prob_corners_over * 0.95 if prob_corners_over > 0 else 0,
        )

    return analise


def _adicionar_se_valido(
    analise: BetAnalysis,
    mercado: str,
    predicao: str,
    prob: float,
    odds_minima: float,
) -> None:
    if prob <= 0 or prob >= 1:
        return
    analise.recomendacoes.append(
        BetRecommendation(
            mercado=mercado,
            predicao=predicao,
            probabilidade=round(prob * 100, 1),
            odds_minima=round(odds_minima, 2),
        )
    )
