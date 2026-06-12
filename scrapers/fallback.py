"""Fallback de coleta via Gemini com Google Search — ultimo recurso (RN-13).

Acionado uma unica vez por consulta, apenas se faltarem campos criticos.
Usa a ferramenta de busca nativa do Gemini (google_search) para buscar dados reais.
"""

import json
import logging
import re
from typing import Optional

import config
from models.match_data import GameResult, MatchData, Scorer, TeamData

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Voce e um coletor de dados esportivos. Retorne APENAS dados que voce "
    "encontrou em fontes reais. Para qualquer dado nao encontrado, use null. "
    "NUNCA estime ou invente valores. Responda APENAS com JSON valido."
)


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
    return None


def _merge_team(team: TeamData, data: dict) -> None:
    """Preenche apenas campos ainda vazios (nunca sobrescreve fonte prioritaria)."""
    if not team.recent_games and data.get("recent_games"):
        for g in data["recent_games"][: config.RECENT_GAMES_LIMIT]:
            try:
                team.recent_games.append(
                    GameResult(
                        date=g.get("date"),
                        home_team=g["home_team"],
                        away_team=g["away_team"],
                        home_score=int(g["home_score"]),
                        away_score=int(g["away_score"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    gs = team.goal_stats
    for attr, key in [
        ("avg_scored", "avg_scored"), ("avg_conceded", "avg_conceded"),
        ("btts_pct", "btts_pct"), ("over_15_pct", "over_15_pct"),
        ("over_25_pct", "over_25_pct"), ("over_35_pct", "over_35_pct"),
    ]:
        if getattr(gs, attr) is None and isinstance(data.get(key), (int, float)):
            setattr(gs, attr, float(data[key]))
    if not team.top_scorers and data.get("top_scorers"):
        for s in data["top_scorers"][: config.TOP_SCORERS_LIMIT]:
            try:
                team.top_scorers.append(Scorer(name=s["name"], goals=int(s["goals"])))
            except (KeyError, TypeError, ValueError):
                continue
    if team.current_streak is None and isinstance(data.get("current_streak"), str):
        team.current_streak = data["current_streak"]


def fill_missing(match_data: MatchData, missing_fields: list[str]) -> MatchData:
    """Uma unica chamada ao Gemini com Google Search cobrindo campos faltantes."""
    if not config.GOOGLE_API_KEY:
        logger.warning("Fallback Gemini indisponivel: GOOGLE_API_KEY ausente")
        return match_data
    try:
        import google.generativeai as genai

        genai.configure(api_key=config.GOOGLE_API_KEY)
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            tools="google_search_retrieval",
        )
        prompt = (
            f"Busque dados reais e atuais sobre os times de futebol "
            f"'{match_data.home_team.name}' e '{match_data.away_team.name}'.\n"
            f"Campos faltantes: {', '.join(missing_fields)}.\n"
            "Responda com JSON no formato:\n"
            '{"home": {"recent_games": [{"date":"YYYY-MM-DD","home_team":"","away_team":"","home_score":0,"away_score":0}],'
            ' "avg_scored": 0.0, "avg_conceded": 0.0, "btts_pct": 0.0, "over_15_pct": 0.0, "over_25_pct": 0.0, "over_35_pct": 0.0,'
            ' "top_scorers": [{"name":"","goals":0}], "current_streak": ""},'
            ' "away": {mesmo formato}}'
        )
        response = model.generate_content(prompt)
        usage = getattr(response, "usage_metadata", None)
        if usage:
            logger.info(
                "Fallback Gemini: %s tokens in, %s out",
                getattr(usage, "prompt_token_count", "?"),
                getattr(usage, "candidates_token_count", "?"),
            )
        text = response.text
        data = _extract_json(text)
        if not data:
            logger.warning("Fallback Gemini: resposta sem JSON parseavel")
            return match_data
        if isinstance(data.get("home"), dict):
            _merge_team(match_data.home_team, data["home"])
        if isinstance(data.get("away"), dict):
            _merge_team(match_data.away_team, data["away"])
        match_data.sources_used.append("gemini_search")
    except Exception as exc:
        logger.warning("Fallback Gemini falhou: %s", exc)
    return match_data
