from scrapers.stats_parsing import parse_statistics_payload


def _payload(items):
    return {"statistics": [{"period": "ALL", "groups": [{"statisticsItems": items}]}]}


def test_parse_stats_basicas_e_avancadas():
    data = _payload([
        {"name": "Corner kicks", "home": "7", "away": "2"},
        {"name": "Yellow cards", "home": "1", "away": "3"},
        {"name": "Ball possession", "home": "61%", "away": "39%"},
        {"name": "Expected goals", "home": "2.31", "away": "0.55"},
        {"name": "Big chances", "home": "4", "away": "1"},
        {"name": "Accurate passes", "home": "512 (91%)", "away": "298 (78%)"},
    ])
    stats = parse_statistics_payload(data)
    assert stats.escanteios_casa == 7
    assert stats.cartoes_amarelos_fora == 3
    assert stats.posse_casa == 61.0
    assert stats.xg_casa == 2.31
    assert stats.big_chances_fora == 1
    assert stats.passes_certos_casa == 512


def test_parse_nao_confunde_big_chances_missed():
    data = _payload([
        {"name": "Big chances missed", "home": "9", "away": "9"},
        {"name": "Corner kicks", "home": "5", "away": "4"},
    ])
    stats = parse_statistics_payload(data)
    assert stats.big_chances_casa is None
    assert stats.escanteios_casa == 5


def test_parse_payload_vazio_retorna_none():
    assert parse_statistics_payload({}) is None
    assert parse_statistics_payload({"statistics": []}) is None


def test_parse_valor_invalido_vira_none_sem_quebrar():
    data = _payload([
        {"name": "Expected goals", "home": "n/a", "away": None},
        {"name": "Corner kicks", "home": "5", "away": "4"},
    ])
    stats = parse_statistics_payload(data)
    assert stats.xg_casa is None
    assert stats.escanteios_casa == 5
