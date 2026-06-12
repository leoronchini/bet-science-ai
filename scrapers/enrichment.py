"""Enriquecimento de contexto via Gemini + Google Search (Copa do Mundo 2026).

Uma unica chamada por consulta busca: escalacao provavel, lesoes, suspensoes,
fase do jogo na Copa e odds 1X2 do mercado. Tudo defensivo — qualquer falha
deixa o MatchData inalterado.
"""

import json
import logging
import re
from typing import Optional

import config
from agent.errors import AIUnavailableError, is_fatal_ai_error
from models.match_data import MarketOdds, MatchData, TeamData

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Voce e um coletor de dados sobre a Copa do Mundo FIFA 2026. Retorne APENAS "
    "dados encontrados em fontes reais e recentes. Para qualquer dado nao "
    "encontrado, use null ou lista vazia. NUNCA estime ou invente valores, "
    "nomes de jogadores ou odds. Responda APENAS com JSON valido."
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
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except ValueError:
            return None
    return None


def _str_list(value, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()][:limit]


def _merge_team(team: TeamData, data: dict) -> None:
    if not team.probable_lineup:
        team.probable_lineup = _str_list(data.get("probable_lineup"), 11)
    if not team.injuries:
        team.injuries = _str_list(data.get("injuries"), 10)
    if not team.suspensions:
        team.suspensions = _str_list(data.get("suspensions"), 10)


def _parse_odds(data: dict) -> Optional[MarketOdds]:
    raw = data.get("market_odds_1x2")
    if not isinstance(raw, dict):
        return None
    try:
        odds = MarketOdds(
            home=float(raw["home"]),
            draw=float(raw["draw"]),
            away=float(raw["away"]),
            bookmaker=raw.get("bookmaker") if isinstance(raw.get("bookmaker"), str) else None,
        )
    except (KeyError, TypeError, ValueError):
        return None
    # sanidade: odds decimais validas e overround tipico (1.0 a 1.2)
    if min(odds.home, odds.draw, odds.away) <= 1.01:
        return None
    overround = 1 / odds.home + 1 / odds.draw + 1 / odds.away
    if not 0.95 <= overround <= 1.25:
        logger.warning("Enrichment: odds com overround atipico (%.2f) — descartadas", overround)
        return None
    return odds


def enrich(match_data: MatchData) -> MatchData:
    """Busca contexto da partida da Copa 2026. Mutates e retorna match_data."""
    if not (config.ENABLE_ENRICHMENT and config.GOOGLE_API_KEY):
        return match_data
    home, away = match_data.home_team.name, match_data.away_team.name
    try:
        import google.generativeai as genai

        genai.configure(api_key=config.GOOGLE_API_KEY)
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            tools="google_search_retrieval",
        )
        prompt = (
            f"Partida da Copa do Mundo 2026: {home} x {away}.\n"
            "Busque informacoes ATUAIS sobre este jogo especifico:\n"
            "1. Escalacao provavel (11 titulares) de cada selecao.\n"
            "2. Jogadores lesionados (fora do jogo) de cada selecao.\n"
            "3. Jogadores suspensos de cada selecao.\n"
            "4. Fase do jogo na Copa (Grupos, Oitavas, Quartas, Semifinal, Final).\n"
            "5. Odds decimais 1X2 de casas de apostas para este jogo.\n"
            "Responda com JSON no formato:\n"
            '{"home": {"probable_lineup": [], "injuries": [], "suspensions": []},\n'
            ' "away": {"probable_lineup": [], "injuries": [], "suspensions": []},\n'
            ' "stage": "Grupos"|null,\n'
            ' "market_odds_1x2": {"home": 0.0, "draw": 0.0, "away": 0.0, "bookmaker": ""}|null}'
        )
        response = model.generate_content(prompt)
        usage = getattr(response, "usage_metadata", None)
        if usage:
            logger.info(
                "Enrichment Gemini: %s tokens in, %s out",
                getattr(usage, "prompt_token_count", "?"),
                getattr(usage, "candidates_token_count", "?"),
            )
        data = _extract_json(response.text)
        if not data:
            logger.warning("Enrichment: resposta sem JSON parseavel")
            return match_data
        if isinstance(data.get("home"), dict):
            _merge_team(match_data.home_team, data["home"])
        if isinstance(data.get("away"), dict):
            _merge_team(match_data.away_team, data["away"])
        if match_data.stage is None and isinstance(data.get("stage"), str):
            match_data.stage = data["stage"].strip() or None
        if match_data.odds is None:
            match_data.odds = _parse_odds(data)
        if "gemini_enrichment" not in match_data.sources_used:
            match_data.sources_used.append("gemini_enrichment")
    except Exception as exc:
        if is_fatal_ai_error(exc):
            raise AIUnavailableError(f"Gemini indisponivel no enriquecimento: {exc}") from exc
        logger.warning("Enrichment Gemini falhou: %s", exc)
    return match_data
