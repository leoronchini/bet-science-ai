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


def _evento(eid, casa, fora, gc, gf, ts=1763424000):
    return {
        "id": eid,
        "homeTeam": {"name": casa}, "awayTeam": {"name": fora},
        "homeScore": {"current": gc}, "awayScore": {"current": gf},
        "startTimestamp": ts, "tournament": {"name": "Amistoso"},
        "status": {"type": "finished"},
    }


@responses.activate
def test_search_team_prioriza_selecao_nacional():
    responses.get(
        f"{API}/search/all",
        json={"results": [
            {"type": "team", "entity": {"id": 1, "name": "Japan FC",
             "national": False, "sport": {"slug": "football"}}},
            {"type": "team", "entity": {"id": 4922, "name": "Japan",
             "national": True, "sport": {"slug": "football"}}},
        ]},
    )
    client = SportAPI7Client()
    assert client.search_team("Japan", national=True) == (4922, "Japan")


@responses.activate
def test_eventos_historicos_pagina_ate_o_fim():
    responses.get(
        f"{API}/team/4705/events/last/0",
        json={"events": [_evento(10, "Netherlands", "Japan", 2, 1)],
              "hasNextPage": True},
    )
    responses.get(
        f"{API}/team/4705/events/last/1",
        json={"events": [_evento(11, "Sweden", "Netherlands", 0, 3)],
              "hasNextPage": False},
    )
    client = SportAPI7Client()
    eventos = client.eventos_historicos(4705)
    assert [e["id"] for e in eventos] == [10, 11]


@responses.activate
def test_fetch_event_statistics_com_xg():
    responses.get(
        f"{API}/event/10/statistics",
        json={"statistics": [{"period": "ALL", "groups": [{"statisticsItems": [
            {"name": "Corner kicks", "home": "7", "away": "2"},
            {"name": "Expected goals", "home": "2.31", "away": "0.55"},
        ]}]}]},
    )
    client = SportAPI7Client()
    stats = client.fetch_event_statistics(10)
    assert stats.escanteios_casa == 7
    assert stats.xg_fora == 0.55


@responses.activate
def test_fetch_event_lineups():
    responses.get(
        f"{API}/event/10/lineups",
        json={
            "home": {"players": [{
                "player": {"id": 70996, "name": "Memphis Depay", "position": "F"},
                "statistics": {"minutesPlayed": 90, "goals": 2,
                               "goalAssist": 1, "rating": 8.4,
                               "onTargetScoringAttempt": 3},
            }]},
            "away": {"players": [{
                "player": {"id": 12345, "name": "Wataru Endo", "position": "M"},
                "statistics": {"minutesPlayed": 90, "rating": 6.9},
            }]},
        },
    )
    client = SportAPI7Client()
    jogadores = client.fetch_event_lineups(10)
    assert len(jogadores) == 2
    depay = jogadores[0]
    assert depay.nome == "Memphis Depay"
    assert depay.sofascore_id == 70996
    assert depay.time == "casa"
    assert depay.gols == 2
    assert depay.chutes == 3
    endo = jogadores[1]
    assert endo.time == "fora"
    assert endo.gols is None
