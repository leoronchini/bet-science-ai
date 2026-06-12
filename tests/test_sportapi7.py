import responses
import pytest

import config
from scrapers import sportapi7
from scrapers.sportapi7 import QuotaExceededError, SportAPI7Client

API = f"https://{config.SPORTAPI7_HOST}/api/v1"


@pytest.fixture(autouse=True)
def _ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAPIDAPI_KEY", "chave-teste")
    monkeypatch.setattr(config, "SPORTAPI7_DELAY", 0)
    monkeypatch.setattr(sportapi7, "CACHE_DIR", str(tmp_path / "cache"))
    # neutraliza o backoff exponencial nos testes de 429
    monkeypatch.setattr(sportapi7.time, "sleep", lambda s: None)


@responses.activate
def test_get_envia_headers_rapidapi():
    responses.get(f"{API}/ping", json={"ok": True})
    client = SportAPI7Client()
    assert client._get("/ping") == {"ok": True}
    pedido = responses.calls[0].request
    assert pedido.headers["x-rapidapi-key"] == "chave-teste"
    assert pedido.headers["x-rapidapi-host"] == config.SPORTAPI7_HOST
    assert client.chamadas_api == 1


@responses.activate
def test_cache_evita_segunda_chamada():
    responses.get(f"{API}/ping", json={"ok": True})
    client = SportAPI7Client()
    client._get("/ping")
    client._get("/ping")  # segunda: deve vir do disco
    assert len(responses.calls) == 1
    assert client.chamadas_api == 1
    assert client.chamadas_cache == 1


@responses.activate
def test_429_persistente_levanta_quota_error():
    for _ in range(config.SPORTAPI7_MAX_RETRIES):
        responses.get(f"{API}/ping", status=429)
    client = SportAPI7Client()
    with pytest.raises(QuotaExceededError):
        client._get("/ping")


@responses.activate
def test_401_falha_rapido_com_mensagem_clara():
    responses.get(f"{API}/ping", status=401)
    client = SportAPI7Client()
    with pytest.raises(RuntimeError, match="RAPIDAPI_KEY"):
        client._get("/ping")


def test_sem_chave_falha_antes_da_rede(monkeypatch):
    monkeypatch.setattr(config, "RAPIDAPI_KEY", "")
    client = SportAPI7Client()
    with pytest.raises(RuntimeError, match="RAPIDAPI_KEY"):
        client._get("/ping")


@responses.activate
def test_limite_de_chamadas_para_graciosamente():
    responses.get(f"{API}/a", json={})
    client = SportAPI7Client(limite_chamadas=1)
    client._get("/a")
    with pytest.raises(QuotaExceededError, match="limite"):
        client._get("/b")


@responses.activate
def test_404_retorna_none():
    responses.get(f"{API}/ping", status=404)
    client = SportAPI7Client()
    assert client._get("/ping") is None
