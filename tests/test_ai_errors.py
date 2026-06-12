"""Testes da politica de erro fatal de IA (quota/indisponibilidade encerra)."""

import pytest

from agent.errors import AIUnavailableError, is_fatal_ai_error


def test_quota_429_is_fatal():
    exc = RuntimeError(
        "429 You exceeded your current quota, please check your plan and billing details."
    )
    assert is_fatal_ai_error(exc) is True


def test_resource_exhausted_is_fatal():
    assert is_fatal_ai_error(RuntimeError("RESOURCE_EXHAUSTED")) is True


def test_invalid_key_is_fatal():
    assert is_fatal_ai_error(RuntimeError("API key not valid. API_KEY_INVALID")) is True


def test_generic_error_is_not_fatal():
    assert is_fatal_ai_error(RuntimeError("connection reset by peer")) is False
    assert is_fatal_ai_error(ValueError("resposta sem JSON")) is False


def test_enrichment_raises_on_quota_error(monkeypatch):
    import config
    from models.match_data import MatchData, TeamData
    from scrapers import enrichment

    class FakeModel:
        def __init__(self, *a, **kw):
            pass

        def generate_content(self, *a, **kw):
            raise RuntimeError("429 You exceeded your current quota")

    import google.generativeai as genai

    monkeypatch.setattr(config, "GOOGLE_API_KEY", "fake")
    monkeypatch.setattr(config, "ENABLE_ENRICHMENT", True)
    monkeypatch.setattr(genai, "configure", lambda **kw: None)
    monkeypatch.setattr(genai, "GenerativeModel", FakeModel)

    match = MatchData(home_team=TeamData(name="A"), away_team=TeamData(name="B"))
    with pytest.raises(AIUnavailableError):
        enrichment.enrich(match)


def test_enrichment_swallows_transient_error(monkeypatch):
    import config
    from models.match_data import MatchData, TeamData
    from scrapers import enrichment

    class FakeModel:
        def __init__(self, *a, **kw):
            pass

        def generate_content(self, *a, **kw):
            raise RuntimeError("connection reset by peer")

    import google.generativeai as genai

    monkeypatch.setattr(config, "GOOGLE_API_KEY", "fake")
    monkeypatch.setattr(config, "ENABLE_ENRICHMENT", True)
    monkeypatch.setattr(genai, "configure", lambda **kw: None)
    monkeypatch.setattr(genai, "GenerativeModel", FakeModel)

    match = MatchData(home_team=TeamData(name="A"), away_team=TeamData(name="B"))
    result = enrichment.enrich(match)  # nao deve levantar
    assert result is match
