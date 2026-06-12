"""Testes do health check de inicializacao da IA."""

from unittest.mock import MagicMock, patch

from agent import agent


def test_health_check_fails_without_api_key():
    with patch.object(agent.config, "GOOGLE_API_KEY", ""):
        ok, message = agent.health_check()
    assert ok is False
    assert "GOOGLE_API_KEY" in message


def test_health_check_success():
    response = MagicMock(text="pong")
    model = MagicMock()
    model.generate_content.return_value = response
    with patch.object(agent.config, "GOOGLE_API_KEY", "fake-key"), \
         patch("google.generativeai.GenerativeModel", return_value=model), \
         patch("google.generativeai.configure"):
        ok, message = agent.health_check()
    assert ok is True
    assert "disponivel" in message


def test_health_check_fails_on_api_error():
    model = MagicMock()
    model.generate_content.side_effect = RuntimeError("quota exceeded")
    with patch.object(agent.config, "GOOGLE_API_KEY", "fake-key"), \
         patch("google.generativeai.GenerativeModel", return_value=model), \
         patch("google.generativeai.configure"):
        ok, message = agent.health_check()
    assert ok is False
    assert "quota exceeded" in message


def test_health_check_fails_on_empty_response():
    response = MagicMock(text="")
    model = MagicMock()
    model.generate_content.return_value = response
    with patch.object(agent.config, "GOOGLE_API_KEY", "fake-key"), \
         patch("google.generativeai.GenerativeModel", return_value=model), \
         patch("google.generativeai.configure"):
        ok, message = agent.health_check()
    assert ok is False
    assert "vazio" in message
