import sqlite3

import pytest

from models.match_data import MatchStats, PlayerMatchStats
from preditivo.data import database


SCHEMA_ANTIGO = """
CREATE TABLE times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    nome_canonico TEXT,
    sofascore_id INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE partidas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time_casa_id INTEGER NOT NULL REFERENCES times(id),
    time_fora_id INTEGER NOT NULL REFERENCES times(id),
    data TEXT, competicao TEXT, gols_casa INTEGER, gols_fora INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(time_casa_id, time_fora_id, data)
);
CREATE TABLE estatisticas_detalhadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partida_id INTEGER NOT NULL REFERENCES partidas(id),
    escanteios_casa INTEGER, escanteios_fora INTEGER,
    cartoes_amarelos_casa INTEGER, cartoes_amarelos_fora INTEGER,
    cartoes_vermelhos_casa INTEGER, cartoes_vermelhos_fora INTEGER,
    posse_casa REAL, posse_fora REAL,
    chutes_gol_casa INTEGER, chutes_gol_fora INTEGER,
    faltas_casa INTEGER, faltas_fora INTEGER,
    impedimentos_casa INTEGER, impedimentos_fora INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(partida_id)
);
"""


@pytest.fixture
def db_tmp(tmp_path, monkeypatch):
    caminho = str(tmp_path / "teste.db")
    monkeypatch.setattr(database, "_DB_PATH", caminho)
    return caminho


def _colunas(caminho, tabela):
    with sqlite3.connect(caminho) as conn:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}


def test_init_db_banco_novo_tem_schema_completo(db_tmp):
    database.init_db()
    assert "xg_casa" in _colunas(db_tmp, "estatisticas_detalhadas")
    assert "passes_certos_fora" in _colunas(db_tmp, "estatisticas_detalhadas")
    assert "sofascore_id" in _colunas(db_tmp, "jogadores")
    assert "nota" in _colunas(db_tmp, "estatisticas_jogadores")


def test_init_db_migra_banco_legado_sem_perder_dados(db_tmp):
    with sqlite3.connect(db_tmp) as conn:
        conn.executescript(SCHEMA_ANTIGO)
        conn.execute("INSERT INTO times (nome) VALUES ('Holanda')")
    database.init_db()  # nao pode falhar nem apagar dados
    assert "xg_casa" in _colunas(db_tmp, "estatisticas_detalhadas")
    with sqlite3.connect(db_tmp) as conn:
        nomes = [r[0] for r in conn.execute("SELECT nome FROM times")]
    assert nomes == ["Holanda"]
    database.init_db()  # idempotente: segunda chamada nao pode falhar


def test_upsert_partida_grava_xg(db_tmp):
    database.init_db()
    casa = database.upsert_time("Holanda", "Netherlands", 4705)
    fora = database.upsert_time("Japao", "Japan", 4922)
    stats = MatchStats(escanteios_casa=7, escanteios_fora=2, xg_casa=2.31,
                       xg_fora=0.55, big_chances_casa=4, passes_certos_casa=512)
    pid = database.upsert_partida(casa, fora, "2025-11-18", "Amistoso", 3, 0, stats)
    with sqlite3.connect(db_tmp) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM estatisticas_detalhadas WHERE partida_id = ?", (pid,)
        ).fetchone()
    assert row["xg_casa"] == 2.31
    assert row["big_chances_casa"] == 4
    assert row["escanteios_casa"] == 7


def test_upsert_jogador_idempotente(db_tmp):
    database.init_db()
    time_id = database.upsert_time("Holanda", "Netherlands", 4705)
    j1 = database.upsert_jogador("Memphis Depay", sofascore_id=70996,
                                 time_id=time_id, posicao="F")
    j2 = database.upsert_jogador("Memphis Depay", sofascore_id=70996)
    assert j1 == j2


def test_upsert_stats_jogador_idempotente(db_tmp):
    database.init_db()
    casa = database.upsert_time("Holanda", "Netherlands", 4705)
    fora = database.upsert_time("Japao", "Japan", 4922)
    pid = database.upsert_partida(casa, fora, "2025-11-18", "Amistoso", 3, 0)
    jid = database.upsert_jogador("Memphis Depay", sofascore_id=70996)
    p = PlayerMatchStats(nome="Memphis Depay", minutos=90, gols=2, nota=8.4)
    database.upsert_stats_jogador(pid, jid, p)
    p.gols = 3
    database.upsert_stats_jogador(pid, jid, p)  # atualiza, nao duplica
    with sqlite3.connect(db_tmp) as conn:
        rows = conn.execute(
            "SELECT gols FROM estatisticas_jogadores WHERE partida_id=?", (pid,)
        ).fetchall()
    assert rows == [(3,)]
