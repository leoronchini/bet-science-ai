from coletar_copa import GRUPO_F, extrair_adversarios


def test_grupo_f_completo():
    assert GRUPO_F == ["Netherlands", "Japan", "Sweden", "Tunisia"]


def test_extrair_adversarios_ignora_proprio_grupo():
    eventos = [
        {"homeTeam": {"name": "Netherlands"}, "awayTeam": {"name": "France"}},
        {"homeTeam": {"name": "Japan"}, "awayTeam": {"name": "Netherlands"}},
        {"homeTeam": {"name": "Tunisia"}, "awayTeam": {"name": "Brazil"}},
        {"homeTeam": {"name": "France"}, "awayTeam": {"name": "Sweden"}},
    ]
    advs = extrair_adversarios(eventos, GRUPO_F)
    assert advs == {"Brazil", "France"}
