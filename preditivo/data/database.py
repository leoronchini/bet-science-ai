import logging
import os
import sqlite3
from typing import Optional

from models.match_data import GameResult, MatchStats, PlayerMatchStats

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
        _migrar(conn)
    logger.info("Banco inicializado em %s", _DB_PATH)


_COLUNAS_NOVAS_STATS = [
    ("xg_casa", "REAL"), ("xg_fora", "REAL"),
    ("big_chances_casa", "INTEGER"), ("big_chances_fora", "INTEGER"),
    ("passes_certos_casa", "INTEGER"), ("passes_certos_fora", "INTEGER"),
]


def _migrar(conn: sqlite3.Connection) -> None:
    """ALTER TABLE idempotente para bancos criados antes do schema estendido."""
    existentes = {r[1] for r in conn.execute("PRAGMA table_info(estatisticas_detalhadas)")}
    for nome, tipo in _COLUNAS_NOVAS_STATS:
        if nome not in existentes:
            conn.execute(f"ALTER TABLE estatisticas_detalhadas ADD COLUMN {nome} {tipo}")


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
        conn.execute(
            """INSERT INTO partidas (time_casa_id, time_fora_id, data, competicao, gols_casa, gols_fora)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(time_casa_id, time_fora_id, data) DO UPDATE SET
                   gols_casa=excluded.gols_casa, gols_fora=excluded.gols_fora,
                   competicao=COALESCE(excluded.competicao, partidas.competicao)""",
            (time_casa_id, time_fora_id, data, competicao, gols_casa, gols_fora),
        )
        if data is None:
            row = conn.execute(
                "SELECT id FROM partidas WHERE time_casa_id=? AND time_fora_id=? AND data IS NULL",
                (time_casa_id, time_fora_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM partidas WHERE time_casa_id=? AND time_fora_id=? AND data=?",
                (time_casa_id, time_fora_id, data),
            ).fetchone()
        partida_id = row["id"]

        if stats:
            upsert_stats(conn, partida_id, stats)

        return partida_id


def upsert_stats(conn: sqlite3.Connection, partida_id: int, stats: MatchStats) -> None:
    conn.execute(
        """INSERT INTO estatisticas_detalhadas
           (partida_id, escanteios_casa, escanteios_fora,
            cartoes_amarelos_casa, cartoes_amarelos_fora,
            cartoes_vermelhos_casa, cartoes_vermelhos_fora,
            posse_casa, posse_fora, chutes_gol_casa, chutes_gol_fora,
            faltas_casa, faltas_fora, impedimentos_casa, impedimentos_fora,
            xg_casa, xg_fora, big_chances_casa, big_chances_fora,
            passes_certos_casa, passes_certos_fora)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
               impedimentos_fora=excluded.impedimentos_fora,
               xg_casa=COALESCE(excluded.xg_casa, estatisticas_detalhadas.xg_casa),
               xg_fora=COALESCE(excluded.xg_fora, estatisticas_detalhadas.xg_fora),
               big_chances_casa=COALESCE(excluded.big_chances_casa, estatisticas_detalhadas.big_chances_casa),
               big_chances_fora=COALESCE(excluded.big_chances_fora, estatisticas_detalhadas.big_chances_fora),
               passes_certos_casa=COALESCE(excluded.passes_certos_casa, estatisticas_detalhadas.passes_certos_casa),
               passes_certos_fora=COALESCE(excluded.passes_certos_fora, estatisticas_detalhadas.passes_certos_fora)""",
        (
            partida_id,
            stats.escanteios_casa, stats.escanteios_fora,
            stats.cartoes_amarelos_casa, stats.cartoes_amarelos_fora,
            stats.cartoes_vermelhos_casa, stats.cartoes_vermelhos_fora,
            stats.posse_casa, stats.posse_fora,
            stats.chutes_gol_casa, stats.chutes_gol_fora,
            stats.faltas_casa, stats.faltas_fora,
            stats.impedimentos_casa, stats.impedimentos_fora,
            stats.xg_casa, stats.xg_fora,
            stats.big_chances_casa, stats.big_chances_fora,
            stats.passes_certos_casa, stats.passes_certos_fora,
        ),
    )


def upsert_jogador(
    nome: str,
    sofascore_id: Optional[int] = None,
    time_id: Optional[int] = None,
    posicao: Optional[str] = None,
) -> int:
    with _conectar() as conn:
        if sofascore_id is not None:
            conn.execute(
                """INSERT INTO jogadores (nome, sofascore_id, time_id, posicao)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(sofascore_id) DO UPDATE SET
                       nome=excluded.nome,
                       time_id=COALESCE(excluded.time_id, jogadores.time_id),
                       posicao=COALESCE(excluded.posicao, jogadores.posicao)""",
                (nome, sofascore_id, time_id, posicao),
            )
            row = conn.execute(
                "SELECT id FROM jogadores WHERE sofascore_id = ?", (sofascore_id,)
            ).fetchone()
            return row["id"]
        cur = conn.execute(
            "INSERT INTO jogadores (nome, time_id, posicao) VALUES (?, ?, ?)",
            (nome, time_id, posicao),
        )
        return cur.lastrowid


def upsert_stats_jogador(partida_id: int, jogador_id: int, p: PlayerMatchStats) -> None:
    with _conectar() as conn:
        conn.execute(
            """INSERT INTO estatisticas_jogadores
               (partida_id, jogador_id, minutos, gols, assistencias,
                cartao_amarelo, cartao_vermelho, chutes, nota)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(partida_id, jogador_id) DO UPDATE SET
                   minutos=excluded.minutos, gols=excluded.gols,
                   assistencias=excluded.assistencias,
                   cartao_amarelo=excluded.cartao_amarelo,
                   cartao_vermelho=excluded.cartao_vermelho,
                   chutes=excluded.chutes, nota=excluded.nota""",
            (
                partida_id, jogador_id, p.minutos, p.gols, p.assistencias,
                p.cartao_amarelo, p.cartao_vermelho, p.chutes, p.nota,
            ),
        )


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
