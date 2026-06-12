import logging
import os
import sqlite3
from typing import Optional

from models.match_data import GameResult, MatchStats

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "preditivo.db")


def _conectar() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    schema = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema) as f:
        ddl = f.read()
    with _conectar() as conn:
        conn.executescript(ddl)
    logger.info("Banco inicializado em %s", _DB_PATH)


def upsert_time(nome: str, nome_canonico: str = "", sofascore_id: Optional[int] = None) -> int:
    with _conectar() as conn:
        cur = conn.execute(
            """INSERT INTO times (nome, nome_canonico, sofascore_id)
               VALUES (?, ?, ?)
               ON CONFLICT(nome) DO UPDATE SET
                   nome_canonico=COALESCE(excluded.nome_canonico, times.nome_canonico),
                   sofascore_id=COALESCE(excluded.sofascore_id, times.sofascore_id)""",
            (nome, nome_canonico, sofascore_id),
        )
        return cur.lastrowid


def upsert_partida(
    time_casa_id: int,
    time_fora_id: int,
    data: Optional[str],
    competicao: Optional[str],
    gols_casa: int,
    gols_fora: int,
    stats: Optional[MatchStats] = None,
) -> int:
    with _conectar() as conn:
        cur = conn.execute(
            """INSERT INTO partidas (time_casa_id, time_fora_id, data, competicao, gols_casa, gols_fora)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(time_casa_id, time_fora_id, data) DO UPDATE SET
                   gols_casa=excluded.gols_casa, gols_fora=excluded.gols_fora,
                   competicao=COALESCE(excluded.competicao, partidas.competicao)""",
            (time_casa_id, time_fora_id, data, competicao, gols_casa, gols_fora),
        )
        partida_id = cur.lastrowid

        if stats:
            conn.execute(
                """INSERT INTO estatisticas_detalhadas
                   (partida_id, escanteios_casa, escanteios_fora,
                    cartoes_amarelos_casa, cartoes_amarelos_fora,
                    cartoes_vermelhos_casa, cartoes_vermelhos_fora,
                    posse_casa, posse_fora,
                    chutes_gol_casa, chutes_gol_fora,
                    faltas_casa, faltas_fora,
                    impedimentos_casa, impedimentos_fora)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(partida_id) DO UPDATE SET
                       escanteios_casa=excluded.escanteios_casa,
                       escanteios_fora=excluded.escanteios_fora,
                       cartoes_amarelos_casa=excluded.cartoes_amarelos_casa,
                       cartoes_amarelos_fora=excluded.cartoes_amarelos_fora,
                       cartoes_vermelhos_casa=excluded.cartoes_vermelhos_casa,
                       cartoes_vermelhos_fora=excluded.cartoes_vermelhos_fora,
                       posse_casa=excluded.posse_casa, posse_fora=excluded.posse_fora,
                       chutes_gol_casa=excluded.chutes_gol_casa,
                       chutes_gol_fora=excluded.chutes_gol_fora,
                       faltas_casa=excluded.faltas_casa, faltas_fora=excluded.faltas_fora,
                       impedimentos_casa=excluded.impedimentos_casa,
                       impedimentos_fora=excluded.impedimentos_fora""",
                (
                    partida_id,
                    stats.escanteios_casa, stats.escanteios_fora,
                    stats.cartoes_amarelos_casa, stats.cartoes_amarelos_fora,
                    stats.cartoes_vermelhos_casa, stats.cartoes_vermelhos_fora,
                    stats.posse_casa, stats.posse_fora,
                    stats.chutes_gol_casa, stats.chutes_gol_fora,
                    stats.faltas_casa, stats.faltas_fora,
                    stats.impedimentos_casa, stats.impedimentos_fora,
                ),
            )

        return partida_id


def salvar_predicao(
    partida_id: int,
    modelo: str,
    prob_casa: float,
    prob_empate: float,
    prob_fora: float,
    xg_casa: Optional[float],
    xg_fora: Optional[float],
    escanteios_casa: Optional[float],
    escanteios_fora: Optional[float],
    cartoes_casa: Optional[float],
    cartoes_fora: Optional[float],
    prob_over_25: Optional[float],
    prob_btts: Optional[float],
) -> None:
    with _conectar() as conn:
        conn.execute(
            """INSERT INTO predicoes
               (partida_id, modelo, prob_casa, prob_empate, prob_fora,
                xg_casa, xg_fora, escanteios_casa, escanteios_fora,
                cartoes_casa, cartoes_fora, prob_over_25, prob_btts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                partida_id, modelo, prob_casa, prob_empate, prob_fora,
                xg_casa, xg_fora, escanteios_casa, escanteios_fora,
                cartoes_casa, cartoes_fora, prob_over_25, prob_btts,
            ),
        )


def buscar_partidas_sem_stats(limite: int = 100) -> list[dict]:
    with _conectar() as conn:
        rows = conn.execute(
            """SELECT p.id, p.time_casa_id, p.time_fora_id, p.data, p.competicao,
                      p.gols_casa, p.gols_fora,
                      tc.nome AS casa_nome, tf.nome AS fora_nome,
                      tc.sofascore_id AS casa_sf_id, tf.sofascore_id AS fora_sf_id
               FROM partidas p
               JOIN times tc ON tc.id = p.time_casa_id
               JOIN times tf ON tf.id = p.time_fora_id
               LEFT JOIN estatisticas_detalhadas e ON e.partida_id = p.id
               WHERE e.id IS NULL
               ORDER BY p.data DESC
               LIMIT ?""",
            (limite,),
        ).fetchall()
        return [dict(r) for r in rows]


def buscar_todas_partidas() -> list[dict]:
    with _conectar() as conn:
        rows = conn.execute(
            """SELECT p.*, tc.nome AS casa_nome, tf.nome AS fora_nome,
                      e.*
               FROM partidas p
               JOIN times tc ON tc.id = p.time_casa_id
               JOIN times tf ON tf.id = p.time_fora_id
               LEFT JOIN estatisticas_detalhadas e ON e.partida_id = p.id
               ORDER BY p.data DESC""",
        ).fetchall()
        return [dict(r) for r in rows]


def obter_time_por_nome(nome: str) -> Optional[dict]:
    with _conectar() as conn:
        row = conn.execute(
            "SELECT * FROM times WHERE nome = ?", (nome,)
        ).fetchone()
        return dict(row) if row else None
