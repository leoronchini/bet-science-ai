from models.match_data import MatchStats, PlayerMatchStats


def test_matchstats_tem_campos_avancados():
    stats = MatchStats(xg_casa=1.42, xg_fora=0.77, big_chances_casa=3,
                       big_chances_fora=1, passes_certos_casa=480,
                       passes_certos_fora=302)
    assert stats.xg_casa == 1.42
    assert stats.big_chances_fora == 1
    assert stats.passes_certos_casa == 480


def test_matchstats_avancados_default_none():
    stats = MatchStats()
    assert stats.xg_casa is None
    assert stats.big_chances_casa is None
    assert stats.passes_certos_fora is None


def test_player_match_stats():
    p = PlayerMatchStats(nome="Memphis Depay", sofascore_id=70996,
                         posicao="F", time="casa", minutos=90, gols=2,
                         assistencias=1, chutes=5, nota=8.4)
    assert p.nome == "Memphis Depay"
    assert p.cartao_amarelo is None
    assert p.gols == 2
