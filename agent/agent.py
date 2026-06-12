"""Unica interface com o Google Gemini para analise (AD-05).

Em qualquer falha, retorna a predicao-base Poisson inalterada.
"""

import json
import logging
import re
from typing import Optional

import config
from agent.errors import AIUnavailableError, is_fatal_ai_error
from models.match_data import MatchData, Prediction, ScorePrediction

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Voce e um analista estatistico especializado na Copa do Mundo FIFA 2026.
Voce recebe:
1. Dados reais coletados (JSON) — forma, gols, H2H, artilheiros, xG, escalacao
   provavel, lesoes, suspensoes, descanso/calendario, fase na Copa e odds de
   mercado, quando disponiveis.
2. Uma predicao-base calculada por modelo Dixon-Coles (Poisson corrigido) ja
   ajustada por contexto (fadiga, mata-mata, desfalques) e odds de mercado.

Sua tarefa:
A) Refinar a predicao-base considerando fatores qualitativos que o modelo
   nao captura (momento/streak, H2H, peso da camisa em Copas, desfalques
   especificos, estilo de jogo das selecoes).
B) Escrever uma analise narrativa em portugues sobre a partida (campo "narrative").
C) Avaliar sua propria confianca nos dados recebidos (campo "ai_confidence").

REGRAS INVIOLAVEIS:
- Use APENAS os dados fornecidos. Nao busque nem presuma dados externos.
- Campos null/ausentes: ignore-os; nao os substitua por estimativas.
- Ajustes maximos de +-10 pontos percentuais sobre a predicao-base.
- win_home_pct + draw_pct + win_away_pct = 100 exatamente.
- Responda APENAS com o JSON no schema fornecido, sem texto adicional.

INSTRUCOES PARA "narrative":
- 1 paragrafo unico e conciso, de 4 a 6 frases, em portugues corrido
  (sem markdown, sem bullets). Maximo ~120 palavras.
- Va direto ao ponto: o essencial da forma recente, o desfalque ou fator de
  contexto mais relevante, 1-2 jogadores de destaque pelo nome, e a
  perspectiva para o jogo. Se houver odds, uma frase sobre o que o mercado espera.
- Nao repita numeros que ja estao na predicao (percentuais, placares).
- Mencione apenas dados presentes no JSON fornecido.

INSTRUCOES PARA "ai_confidence":
- Inteiro de 0 a 100 refletindo a qualidade/completude dos dados recebidos.
- 80-100: dados ricos (forma, xG, H2H, artilheiros, casa/fora todos presentes).
- 50-79: dados parciais (alguns campos ausentes).
- 0-49: dados escassos (forma ou medias de gols ausentes).

Schema da resposta:
{"win_home_pct": float, "draw_pct": float, "win_away_pct": float,
 "xg_home": float|null, "xg_away": float|null,
 "top_scores": [{"score": "2-1", "probability": float}, ...3 itens],
 "over_25_pct": float|null, "btts_pct": float|null,
 "likely_scorers": ["Nome (ABREV)"],
 "reasoning_summary": "max 2 frases",
 "narrative": "texto corrido em portugues",
 "ai_confidence": int}"""


def _extract_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except ValueError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except ValueError:
            return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except ValueError:
            return None
    return None


def _clamp(value: float, base: float) -> float:
    lo = base - config.AI_MAX_ADJUSTMENT
    hi = base + config.AI_MAX_ADJUSTMENT
    return max(lo, min(hi, value))


def _validate(data: dict, base: Prediction, match_data: MatchData) -> Prediction:
    """Validacao anti-hallucination obrigatoria."""
    try:
        win_home = _clamp(float(data["win_home_pct"]), base.win_home_pct)
        draw = _clamp(float(data["draw_pct"]), base.draw_pct)
        win_away = _clamp(float(data["win_away_pct"]), base.win_away_pct)
    except (KeyError, TypeError, ValueError):
        return base

    # fechar soma em 100 (RN-08) distribuindo o residuo SEM violar o clamp
    vals = [win_home, draw, win_away]
    bases = [base.win_home_pct, base.draw_pct, base.win_away_pct]
    diff = 100.0 - sum(vals)
    for i in range(3):
        if abs(diff) < 0.05:
            break
        lo = max(bases[i] - config.AI_MAX_ADJUSTMENT, 0.0)
        hi = bases[i] + config.AI_MAX_ADJUSTMENT
        adjusted = max(lo, min(hi, vals[i] + diff))
        diff -= adjusted - vals[i]
        vals[i] = adjusted
    if abs(diff) >= 0.05:
        return base
    win_home, draw = round(vals[0], 1), round(vals[1], 1)
    win_away = round(100.0 - win_home - draw, 1)

    top_scores = base.top_scores
    raw_scores = data.get("top_scores")
    if isinstance(raw_scores, list) and raw_scores:
        parsed = []
        for item in raw_scores[:3]:
            try:
                parsed.append(ScorePrediction(score=str(item["score"]),
                                              probability=float(item["probability"])))
            except (KeyError, TypeError, ValueError):
                continue
        if len(parsed) == 3:
            top_scores = parsed

    # likely_scorers: apenas nomes presentes nos dados reais (anti-hallucination)
    known = {
        s.name.lower()
        for t in (match_data.home_team, match_data.away_team)
        for s in t.top_scorers
    }
    likely = base.likely_scorers
    raw_likely = data.get("likely_scorers")
    if isinstance(raw_likely, list):
        filtered = [
            s for s in raw_likely
            if isinstance(s, str) and any(name in s.lower() for name in known)
        ]
        if filtered:
            likely = filtered

    def opt_float(key, fallback):
        v = data.get(key)
        return round(float(v), 1) if isinstance(v, (int, float)) else fallback

    narrative = data.get("narrative")
    narrative = narrative.strip() if isinstance(narrative, str) and narrative.strip() else None

    raw_conf = data.get("ai_confidence")
    ai_confidence = int(raw_conf) if isinstance(raw_conf, (int, float)) and 0 <= raw_conf <= 100 else None

    return Prediction(
        xg_home=opt_float("xg_home", base.xg_home),
        xg_away=opt_float("xg_away", base.xg_away),
        win_home_pct=win_home,
        draw_pct=draw,
        win_away_pct=win_away,
        top_scores=top_scores,
        over_25_pct=opt_float("over_25_pct", base.over_25_pct),
        btts_pct=opt_float("btts_pct", base.btts_pct),
        likely_scorers=likely,
        reasoning_summary=data.get("reasoning_summary")
        if isinstance(data.get("reasoning_summary"), str) else None,
        narrative=narrative,
        ai_confidence=ai_confidence,
    )


def health_check() -> tuple[bool, str]:
    """Verifica se o modelo Gemini esta acessivel e respondendo.

    Retorna (ok, mensagem). Chamada minima (poucos tokens) na inicializacao.
    """
    if not config.GOOGLE_API_KEY:
        return False, "GOOGLE_API_KEY nao configurada (.env)"
    try:
        import google.generativeai as genai

        genai.configure(api_key=config.GOOGLE_API_KEY)
        model = genai.GenerativeModel(model_name=config.GEMINI_MODEL)
        response = model.generate_content(
            "ping",
            generation_config={"max_output_tokens": 5},
        )
        if not getattr(response, "text", None):
            return False, f"modelo {config.GEMINI_MODEL} respondeu vazio"
        return True, f"modelo {config.GEMINI_MODEL} disponivel"
    except Exception as exc:
        return False, f"falha ao acessar o modelo {config.GEMINI_MODEL}: {exc}"


class StatsAgent:
    def __init__(self):
        import google.generativeai as genai

        genai.configure(api_key=config.GOOGLE_API_KEY)
        self._model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )

    def analyze(self, match_data: MatchData, base_prediction: Prediction) -> Prediction:
        if not config.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY ausente — usando Poisson puro")
            return base_prediction
        try:
            base_json = json.dumps(
                {
                    "win_home_pct": base_prediction.win_home_pct,
                    "draw_pct": base_prediction.draw_pct,
                    "win_away_pct": base_prediction.win_away_pct,
                    "xg_home": base_prediction.xg_home,
                    "xg_away": base_prediction.xg_away,
                    "top_scores": [
                        {"score": s.score, "probability": s.probability}
                        for s in base_prediction.top_scores
                    ],
                    "over_25_pct": base_prediction.over_25_pct,
                    "btts_pct": base_prediction.btts_pct,
                },
                ensure_ascii=False,
            )
            prompt = (
                f"DADOS COLETADOS:\n{match_data.to_compact_json()}\n\n"
                f"PREDICAO-BASE (Poisson):\n{base_json}"
            )
            response = self._model.generate_content(prompt)
            usage = getattr(response, "usage_metadata", None)
            if usage:
                logger.info(
                    "Gemini analyze: %s tokens in, %s out",
                    getattr(usage, "prompt_token_count", "?"),
                    getattr(usage, "candidates_token_count", "?"),
                )
            text = response.text
            data = _extract_json(text)
            if not data:
                logger.warning("Gemini: resposta sem JSON parseavel — usando Poisson puro")
                return base_prediction
            result = _validate(data, base_prediction, match_data)
            if result.reasoning_summary:
                logger.debug("Gemini reasoning: %s", result.reasoning_summary)
            return result
        except Exception as exc:
            if is_fatal_ai_error(exc):
                raise AIUnavailableError(f"Gemini indisponivel na analise: {exc}") from exc
            logger.warning("Gemini analyze falhou (%s) — usando Poisson puro", exc)
            return base_prediction
