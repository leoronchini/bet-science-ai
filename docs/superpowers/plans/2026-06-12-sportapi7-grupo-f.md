# SportAPI7 — Coleta Copa 2026 Grupo F: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar o SportAPI7 (RapidAPI, dados Sofascore) como fonte primária de coleta histórica para as seleções do Grupo F da Copa 2026 (Holanda, Japão, Suécia, Tunísia), com cache em disco, schema estendido (xG + estatísticas de jogadores) e CLI de coleta idempotente.

**Architecture:** Novo cliente `SportAPI7Client` com a mesma interface do `SofascoreScraper` (mesmos IDs/paths do Sofascore), parsing de statistics extraído para módulo compartilhado, migração idempotente do SQLite e CLI `coletar_copa.py` com orçamento de chamadas e expansão de adversários (profundidade 1).

**Tech Stack:** Python 3.12, requests, sqlite3, pytest + responses (mock HTTP), dotenv.

**Spec:** `docs/superpowers/specs/2026-06-12-sportapi7-grupo-f-design.md`

---

### Task 1: Configuração (chave, delays, limites)

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Adicionar configs do SportAPI7 em `config.py`**

Após a linha `LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")`:

```python
# SportAPI7 (RapidAPI) — fonte primaria de coleta historica
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
SPORTAPI7_HOST = "sportapi7.p.rapidapi.com"
SPORTAPI7_DELAY = float(os.getenv("SPORTAPI7_DELAY", "0.6"))  # s entre chamadas
SPORTAPI7_MAX_RETRIES = 3
OPPONENT_GAMES_LIMIT = 20    # jogos coletados por adversario (profundidade 1)
```

- [ ] **Step 2: Documentar no `.env.example`**

Adicionar ao final:

```
# Chave do RapidAPI (https://rapidapi.com -> My Apps) para o SportAPI7
RAPIDAPI_KEY=
```

- [ ] **Step 3: Ignorar o cache de API no `.gitignore`**

Adicionar ao final:

```
data/cache_api/
```

- [ ] **Step 4: Verificar que nada quebrou e commitar**

Run: `python -c "import config; print(config.SPORTAPI7_HOST)"`
Expected: `sportapi7.p.rapidapi.com`

```bash
git add config.py .env.example .gitignore
git commit -m "feat: config do SportAPI7 (chave, delay, limites)"
```

---

### Task 2: Estender MatchStats e criar PlayerMatchStats

**Files:**
- Modify: `models/match_data.py`
- Test: `tests/test_match_data.py` (novo)

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/test_match_data.py`:

```python
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
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `pytest tests/test_match_data.py -v`
Expected: FAIL — `ImportError: cannot import name 'PlayerMatchStats'`

- [ ] **Step 3: Implementar**

Em `models/match_data.py`, adicionar ao final da classe `MatchStats` (após `impedimentos_fora`):

```python
    # Estatisticas avancadas (SportAPI7) — None quando indisponiveis
    xg_casa: Optional[float] = None
    xg_fora: Optional[float] = None
    big_chances_casa: Optional[int] = None
    big_chances_fora: Optional[int] = None
    passes_certos_casa: Optional[int] = None
    passes_certos_fora: Optional[int] = None
```

(Os campos devem entrar ANTES das `@property` da classe.)

Adicionar novo dataclass após `MatchStats`:

```python
@dataclass
class PlayerMatchStats:
    """Estatisticas de um jogador em uma partida (lineups do SportAPI7)."""

    nome: str
    sofascore_id: Optional[int] = None
    posicao: Optional[str] = None
    time: Optional[str] = None  # "casa" ou "fora"
    minutos: Optional[int] = None
    gols: Optional[int] = None
    assistencias: Optional[int] = None
    cartao_amarelo: Optional[int] = None
    cartao_vermelho: Optional[int] = None
    chutes: Optional[int] = None
    nota: Optional[float] = None
```

- [ ] **Step 4: Rodar e verificar que passa (suite inteira)**

Run: `pytest tests/ -v`
Expected: PASS (todos, incluindo os pré-existentes)

- [ ] **Step 5: Commit**

```bash
git add models/match_data.py tests/test_match_data.py
git commit -m "feat: campos de xG/avancadas em MatchStats e dataclass PlayerMatchStats"
```

---

### Task 3: Migração de schema + helpers de banco

**Files:**
- Modify: `preditivo/data/schema.sql`
- Modify: `preditivo/data/database.py`
- Modify: `preditivo/data/collector.py` (remover SQL duplicado)
- Test: `tests/test_migracao_schema.py` (novo)

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/test_migracao_schema.py`:

```python
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
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `pytest tests/test_migracao_schema.py -v`
Expected: FAIL — tabela `jogadores` inexistente / `upsert_jogador` não definido

- [ ] **Step 3: Atualizar `preditivo/data/schema.sql`**

Em `estatisticas_detalhadas`, adicionar após `impedimentos_fora INTEGER,`:

```sql
    xg_casa REAL,
    xg_fora REAL,
    big_chances_casa INTEGER,
    big_chances_fora INTEGER,
    passes_certos_casa INTEGER,
    passes_certos_fora INTEGER,
```

Adicionar ao final do arquivo:

```sql
CREATE TABLE IF NOT EXISTS jogadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    sofascore_id INTEGER UNIQUE,
    time_id INTEGER REFERENCES times(id),
    posicao TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS estatisticas_jogadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partida_id INTEGER NOT NULL REFERENCES partidas(id),
    jogador_id INTEGER NOT NULL REFERENCES jogadores(id),
    minutos INTEGER,
    gols INTEGER,
    assistencias INTEGER,
    cartao_amarelo INTEGER,
    cartao_vermelho INTEGER,
    chutes INTEGER,
    nota REAL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(partida_id, jogador_id)
);

CREATE INDEX IF NOT EXISTS idx_stats_jog_partida ON estatisticas_jogadores(partida_id);
```

- [ ] **Step 4: Migração idempotente em `database.py`**

O `executescript` do schema só cria tabelas novas (`IF NOT EXISTS`) — bancos
legados precisam de `ALTER TABLE` para as colunas novas. Em
`preditivo/data/database.py`, adicionar após `init_db`:

```python
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
```

E alterar `init_db` para chamar a migração:

```python
def init_db() -> None:
    schema = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema) as f:
        ddl = f.read()
    with _conectar() as conn:
        conn.executescript(ddl)
        _migrar(conn)
    logger.info("Banco inicializado em %s", _DB_PATH)
```

**Atenção:** `init_db` e todas as funções devem ler `_DB_PATH` dinamicamente —
já é o caso (`_conectar` usa o módulo-level `_DB_PATH`), os testes fazem
monkeypatch dele.

- [ ] **Step 5: Extrair `upsert_stats` e gravar campos novos**

Em `database.py`, substituir o bloco `if stats:` dentro de `upsert_partida` por
uma chamada `if stats: upsert_stats(conn, partida_id, stats)` e criar:

```python
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
```

Em `preditivo/data/collector.py`, substituir o corpo inteiro de
`_upsert_stats_partida` (que duplica esse SQL) por:

```python
def _upsert_stats_partida(partida_id: int, stats: MatchStats) -> None:
    """Insere ou atualiza estatisticas detalhadas de uma partida."""
    from preditivo.data.database import _conectar, upsert_stats

    with _conectar() as conn:
        upsert_stats(conn, partida_id, stats)
```

- [ ] **Step 6: Helpers de jogadores em `database.py`**

Adicionar import no topo: `from models.match_data import GameResult, MatchStats, PlayerMatchStats`

```python
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
```

- [ ] **Step 7: Rodar e verificar que passa (suite inteira)**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add preditivo/data/schema.sql preditivo/data/database.py preditivo/data/collector.py tests/test_migracao_schema.py
git commit -m "feat: schema estendido (xG, jogadores) com migracao idempotente"
```

---

### Task 4: Parser compartilhado de statistics (com xG)

**Files:**
- Create: `scrapers/stats_parsing.py`
- Modify: `scrapers/sofascore.py:150-208` (delegar parsing)
- Test: `tests/test_stats_parsing.py` (novo)

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/test_stats_parsing.py`:

```python
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
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `pytest tests/test_stats_parsing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scrapers.stats_parsing'`

- [ ] **Step 3: Implementar `scrapers/stats_parsing.py`**

```python
"""Parsing compartilhado do payload /event/{id}/statistics.

Usado pelo SofascoreScraper e pelo SportAPI7Client (mesmo formato de resposta).
Nomes de estatisticas casados por igualdade exata para nao confundir
"Big chances" com "Big chances missed".
"""

import re
from typing import Optional

from models.match_data import MatchStats

# nome do item -> (prefixo do campo em MatchStats, conversor)
_MAPA = {
    "Corner kicks": ("escanteios", int),
    "Yellow cards": ("cartoes_amarelos", int),
    "Red cards": ("cartoes_vermelhos", int),
    "Ball possession": ("posse", float),
    "Shots on target": ("chutes_gol", int),
    "Fouls": ("faltas", int),
    "Offsides": ("impedimentos", int),
    "Expected goals": ("xg", float),
    "Big chances": ("big_chances", int),
    "Accurate passes": ("passes_certos", int),
}


def _numero(valor) -> Optional[float]:
    """Extrai o primeiro numero de valores como '7', '61%', '512 (91%)'."""
    if valor is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(valor))
    return float(m.group()) if m else None


def parse_statistics_payload(data: dict) -> Optional[MatchStats]:
    groups = []
    for period in data.get("statistics", []):
        if period.get("period") == "ALL":
            groups = period.get("groups", [])
            break

    stats = MatchStats()
    for group in groups:
        for item in group.get("statisticsItems", []):
            mapeado = _MAPA.get(item.get("name", ""))
            if not mapeado:
                continue
            prefixo, conv = mapeado
            casa, fora = _numero(item.get("home")), _numero(item.get("away"))
            setattr(stats, f"{prefixo}_casa", conv(casa) if casa is not None else None)
            setattr(stats, f"{prefixo}_fora", conv(fora) if fora is not None else None)

    has_data = any([
        stats.escanteios_casa, stats.cartoes_amarelos_casa,
        stats.cartoes_vermelhos_casa, stats.posse_casa, stats.xg_casa,
    ])
    return stats if has_data else None
```

- [ ] **Step 4: Delegar em `sofascore.py`**

Substituir o corpo de `SofascoreScraper.fetch_event_statistics` (linhas 150-208) por:

```python
    def fetch_event_statistics(self, event_id: int) -> Optional[MatchStats]:
        """Busca estatisticas detalhadas (escanteios, cartoes, posse, etc)."""
        time.sleep(0.5)
        resp = http_get(f"{API}/event/{event_id}/statistics")
        if resp is None:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        return parse_statistics_payload(data)
```

E adicionar o import no topo: `from scrapers.stats_parsing import parse_statistics_payload`

- [ ] **Step 5: Rodar a suite inteira**

Run: `pytest tests/ -v`
Expected: PASS (atenção especial a `test_orchestrator.py` e `test_stats_calc.py`)

- [ ] **Step 6: Commit**

```bash
git add scrapers/stats_parsing.py scrapers/sofascore.py tests/test_stats_parsing.py
git commit -m "refactor: parser de statistics compartilhado com suporte a xG"
```

---

### Task 5: SportAPI7Client — núcleo HTTP (cache, retries, cota)

**Files:**
- Create: `scrapers/sportapi7.py`
- Test: `tests/test_sportapi7.py` (novo)

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/test_sportapi7.py`:

```python
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
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `pytest tests/test_sportapi7.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scrapers.sportapi7'`

- [ ] **Step 3: Implementar o núcleo em `scrapers/sportapi7.py`**

```python
"""Cliente SportAPI7 (RapidAPI) — fonte primaria de coleta historica.

API comercial sobre os dados do Sofascore: mesmos paths e IDs de
times/eventos do scraper sofascore.py, que permanece como fallback.
Toda resposta 200 e cacheada em disco para nao gastar cota em reprocessos.
"""

import hashlib
import json
import logging
import os
import time
from typing import Optional

import requests

import config
from models.match_data import GameResult, MatchStats, PlayerMatchStats, TeamData
from scrapers import stats_calc
from scrapers.base import BaseScraper
from scrapers.sofascore import _parse_event
from scrapers.stats_parsing import parse_statistics_payload

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join("data", "cache_api")


class QuotaExceededError(RuntimeError):
    """Cota do RapidAPI esgotada ou limite de chamadas da sessao atingido."""


class SportAPI7Client(BaseScraper):
    source_name = "sportapi7"

    def __init__(self, refresh: bool = False, limite_chamadas: Optional[int] = None):
        self.refresh = refresh
        self.limite_chamadas = limite_chamadas
        self.chamadas_api = 0
        self.chamadas_cache = 0

    # ------------------------------------------------------------ HTTP/cache

    def _cache_path(self, path: str) -> str:
        digest = hashlib.sha1(path.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{digest}.json")

    def _get(self, path: str) -> Optional[dict]:
        cache_file = self._cache_path(path)
        if not self.refresh and os.path.exists(cache_file):
            self.chamadas_cache += 1
            with open(cache_file) as f:
                return json.load(f)

        if not config.RAPIDAPI_KEY:
            raise RuntimeError(
                "RAPIDAPI_KEY ausente — configure no .env (veja .env.example)"
            )
        if self.limite_chamadas is not None and self.chamadas_api >= self.limite_chamadas:
            raise QuotaExceededError(
                f"limite de {self.limite_chamadas} chamadas da sessao atingido"
            )

        url = f"https://{config.SPORTAPI7_HOST}/api/v1{path}"
        headers = {
            "x-rapidapi-key": config.RAPIDAPI_KEY,
            "x-rapidapi-host": config.SPORTAPI7_HOST,
        }
        for tentativa in range(config.SPORTAPI7_MAX_RETRIES):
            time.sleep(config.SPORTAPI7_DELAY)
            try:
                resp = requests.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
            except requests.RequestException as exc:
                logger.warning("SportAPI7: falha de rede em %s: %s", path, exc)
                return None
            self.chamadas_api += 1

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    logger.warning("SportAPI7: resposta nao-JSON em %s", path)
                    return None
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(cache_file, "w") as f:
                    json.dump(data, f)
                return data
            if resp.status_code in (401, 403):
                raise RuntimeError(
                    f"SportAPI7 HTTP {resp.status_code}: RAPIDAPI_KEY invalida "
                    "ou sem assinatura ativa — verifique o .env"
                )
            if resp.status_code == 429:
                espera = 2 * (2 ** tentativa)
                logger.warning("SportAPI7: 429 em %s — backoff %ss", path, espera)
                time.sleep(espera)
                continue
            logger.warning("SportAPI7: HTTP %s em %s", resp.status_code, path)
            return None

        raise QuotaExceededError("cota SportAPI7 esgotada (HTTP 429 persistente)")
```

(`_parse_event`, `stats_calc`, `parse_statistics_payload` etc. já ficam
importados para a Task 6; os métodos abstratos `fetch_team_data`/`fetch_h2h`
chegam na Task 6 — para os testes desta task passarem, adicionar stubs
temporários:)

```python
    # implementados na proxima task
    def fetch_team_data(self, team_name: str) -> Optional[TeamData]:
        raise NotImplementedError

    def fetch_h2h(self, home: TeamData, away: TeamData) -> list[GameResult]:
        raise NotImplementedError
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `pytest tests/test_sportapi7.py -v`
Expected: PASS (7 testes)

- [ ] **Step 5: Commit**

```bash
git add scrapers/sportapi7.py tests/test_sportapi7.py
git commit -m "feat: nucleo HTTP do SportAPI7Client com cache, backoff e controle de cota"
```

---

### Task 6: SportAPI7Client — endpoints (busca, histórico, stats, lineups)

**Files:**
- Modify: `scrapers/sportapi7.py`
- Test: `tests/test_sportapi7.py` (ampliar)

- [ ] **Step 1: Escrever testes que falham**

Adicionar ao final de `tests/test_sportapi7.py`:

```python
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
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `pytest tests/test_sportapi7.py -v`
Expected: FAIL — `AttributeError: ... 'search_team'` (e demais métodos)

- [ ] **Step 3: Implementar os endpoints**

Em `scrapers/sportapi7.py`, remover os stubs `NotImplementedError` e adicionar
os métodos à classe:

```python
    # ------------------------------------------------------------- endpoints

    def search_team(self, name: str, national: bool = False) -> Optional[tuple[int, str]]:
        data = self._get(f"/search/all?q={name}")
        if not data:
            return None
        candidatos = []
        for item in data.get("results", []):
            entity = item.get("entity", {})
            if item.get("type") == "team" and entity.get("sport", {}).get("slug") == "football":
                candidatos.append(entity)
        if national:
            nacionais = [e for e in candidatos if e.get("national")]
            candidatos = nacionais or candidatos
        if not candidatos:
            return None
        escolhido = candidatos[0]
        return escolhido.get("id"), escolhido.get("name", name)

    def _last_events(self, team_id: int) -> list[dict]:
        data = self._get(f"/team/{team_id}/events/last/0")
        return data.get("events", []) if data else []

    def eventos_historicos(self, team_id: int, max_paginas: int = 40) -> list[dict]:
        """Pagina /events/last/{p} ate esgotar o historico disponivel."""
        eventos: list[dict] = []
        for pagina in range(max_paginas):
            data = self._get(f"/team/{team_id}/events/last/{pagina}")
            if not data:
                break
            eventos.extend(data.get("events", []))
            if not data.get("hasNextPage"):
                break
        return eventos

    def fetch_event_statistics(self, event_id: int) -> Optional[MatchStats]:
        data = self._get(f"/event/{event_id}/statistics")
        if not data:
            return None
        return parse_statistics_payload(data)

    def fetch_event_lineups(self, event_id: int) -> list[PlayerMatchStats]:
        data = self._get(f"/event/{event_id}/lineups")
        if not data:
            return []
        jogadores = []
        for lado, rotulo in (("home", "casa"), ("away", "fora")):
            for entry in data.get(lado, {}).get("players", []):
                player = entry.get("player", {})
                st = entry.get("statistics") or {}
                jogadores.append(PlayerMatchStats(
                    nome=player.get("name", "?"),
                    sofascore_id=player.get("id"),
                    posicao=player.get("position"),
                    time=rotulo,
                    minutos=st.get("minutesPlayed"),
                    gols=st.get("goals"),
                    assistencias=st.get("goalAssist"),
                    chutes=st.get("onTargetScoringAttempt"),
                    nota=st.get("rating"),
                ))
        return jogadores

    def enrich_events_with_stats(self, events: list[dict]) -> None:
        """Enriquece eventos finalizados com MatchStats in-place (interface sofascore)."""
        for event in events:
            if event.get("status", {}).get("type") != "finished":
                continue
            event_id = event.get("id")
            if not event_id:
                continue
            stats = self.fetch_event_statistics(event_id)
            if stats:
                event["_stats"] = stats

    # ------------------------------------------- interface BaseScraper

    def fetch_team_data(self, team_name: str) -> Optional[TeamData]:
        found = self.search_team(team_name, national=True)
        if not found:
            logger.warning("SportAPI7: time %r nao encontrado", team_name)
            return None
        team_id, canonical = found
        events = self._last_events(team_id)
        finished = [e for e in events if e.get("status", {}).get("type") == "finished"]
        self.enrich_events_with_stats(finished)
        finished.reverse()  # API retorna do mais antigo para o mais recente
        games = [g for g in (_parse_event(e) for e in finished) if g]
        games = games[: config.RECENT_GAMES_LIMIT]

        team = TeamData(name=canonical, resolved_id=str(team_id), recent_games=games)
        team.goal_stats = stats_calc.compute_goal_stats(games, canonical)
        team.home_record = stats_calc.compute_record(games, canonical, home=True)
        team.away_record = stats_calc.compute_record(games, canonical, home=False)
        team.current_streak = stats_calc.compute_streak(games, canonical)
        return team

    def fetch_h2h(self, home: TeamData, away: TeamData) -> list[GameResult]:
        away_lower = away.name.lower()
        mutual = [
            g for g in home.recent_games
            if away_lower in (g.home_team.lower(), g.away_team.lower())
        ]
        return mutual[: config.H2H_LIMIT]
```

- [ ] **Step 4: Rodar a suite inteira**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/sportapi7.py tests/test_sportapi7.py
git commit -m "feat: endpoints do SportAPI7Client (busca nacional, paginacao, xG, lineups)"
```

---

### Task 7: CLI `coletar_copa.py` (Grupo F + adversários)

**Files:**
- Create: `coletar_copa.py`
- Modify: `preditivo/data/collector.py` (persistência de seleção com jogadores)
- Test: `tests/test_coletar_copa.py` (novo)

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/test_coletar_copa.py` (testa as funções puras do módulo; o fluxo
de rede é coberto pelos testes do client + aceite manual):

```python
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
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `pytest tests/test_coletar_copa.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'coletar_copa'`

- [ ] **Step 3: Persistência de seleção em `collector.py`**

Adicionar ao final de `preditivo/data/collector.py` (imports novos no topo:
`from preditivo.data.database import upsert_jogador, upsert_stats_jogador`):

```python
def coletar_selecao(client, nome_selecao: str, com_jogadores: bool = True) -> tuple[int, list[dict]]:
    """Coleta historico completo de uma selecao via SportAPI7.

    Retorna (n_partidas, eventos_finalizados) — os eventos alimentam a
    expansao de adversarios no chamador.
    """
    found = client.search_team(nome_selecao, national=True)
    if not found:
        logger.warning("Selecao nao encontrada: %s", nome_selecao)
        return 0, []
    team_id, canonical = found
    time_db_id = upsert_time(nome_selecao, canonical, team_id)

    eventos = client.eventos_historicos(team_id)
    finished = [e for e in eventos if e.get("status", {}).get("type") == "finished"]

    contador = 0
    for event in finished:
        event_id = event.get("id")
        stats = client.fetch_event_statistics(event_id) if event_id else None
        if stats:
            event["_stats"] = stats

        jogo = _parse_event(event)
        if not jogo:
            continue
        casa_id = _resolver_ou_criar_time(client, jogo.home_team)
        fora_id = _resolver_ou_criar_time(client, jogo.away_team)
        partida_id = upsert_partida(
            time_casa_id=casa_id, time_fora_id=fora_id,
            data=jogo.date, competicao=jogo.competition,
            gols_casa=jogo.home_score, gols_fora=jogo.away_score,
            stats=jogo.stats,
        )
        contador += 1

        if com_jogadores and event_id:
            for p in client.fetch_event_lineups(event_id):
                lado_id = casa_id if p.time == "casa" else fora_id
                jogador_id = upsert_jogador(
                    p.nome, sofascore_id=p.sofascore_id,
                    time_id=lado_id, posicao=p.posicao,
                )
                upsert_stats_jogador(partida_id, jogador_id, p)

    logger.info("Selecao %s: %d partidas coletadas", canonical, contador)
    return contador, finished


def coletar_adversario(client, nome: str, limite_jogos: int) -> int:
    """Ultimos N jogos de um adversario (sem lineups — economiza cota)."""
    found = client.search_team(nome, national=True)
    if not found:
        return 0
    team_id, canonical = found
    upsert_time(nome, canonical, team_id)

    eventos = client._last_events(team_id)
    finished = [e for e in eventos if e.get("status", {}).get("type") == "finished"]
    finished = finished[-limite_jogos:]

    contador = 0
    for event in finished:
        event_id = event.get("id")
        stats = client.fetch_event_statistics(event_id) if event_id else None
        if stats:
            event["_stats"] = stats
        jogo = _parse_event(event)
        if not jogo:
            continue
        casa_id = _resolver_ou_criar_time(client, jogo.home_team)
        fora_id = _resolver_ou_criar_time(client, jogo.away_team)
        upsert_partida(
            time_casa_id=casa_id, time_fora_id=fora_id,
            data=jogo.date, competicao=jogo.competition,
            gols_casa=jogo.home_score, gols_fora=jogo.away_score,
            stats=jogo.stats,
        )
        contador += 1
    return contador
```

Nota: `_resolver_ou_criar_time` e `_parse_event` já existem no módulo
(`from scrapers.sofascore import SofascoreScraper, _parse_event` está no topo).
`_resolver_ou_criar_time(scraper, nome)` só usa `scraper.search_team` — o
`SportAPI7Client` satisfaz a interface por duck typing.

- [ ] **Step 4: Implementar `coletar_copa.py`**

```python
#!/usr/bin/env python3
"""Coleta historica do Grupo F da Copa 2026 via SportAPI7 (RapidAPI).

Idempotente e retomavel: respostas sao cacheadas em data/cache_api/ e os
UNIQUEs do schema evitam duplicatas — rodar de novo continua de onde parou.
"""

import argparse
import logging
import sys

sys.path.insert(0, ".")

from preditivo.data.collector import (
    coletar_adversario,
    coletar_historico_time,
    coletar_selecao,
)
from preditivo.data.database import init_db
from scrapers.sofascore import SofascoreScraper
from scrapers.sportapi7 import QuotaExceededError, SportAPI7Client

import config

logger = logging.getLogger(__name__)

GRUPO_F = ["Netherlands", "Japan", "Sweden", "Tunisia"]


def extrair_adversarios(eventos: list[dict], grupo: list[str]) -> set[str]:
    """Nomes distintos de adversarios encontrados nos eventos do grupo."""
    grupo_lower = {g.lower() for g in grupo}
    adversarios = set()
    for e in eventos:
        for lado in ("homeTeam", "awayTeam"):
            nome = e.get(lado, {}).get("name")
            if nome and nome.lower() not in grupo_lower:
                adversarios.add(nome)
    return adversarios


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta Grupo F Copa 2026 via SportAPI7")
    parser.add_argument("--limite-chamadas", type=int, default=None,
                        help="Maximo de chamadas reais a API nesta sessao")
    parser.add_argument("--refresh", action="store_true",
                        help="Ignora o cache em disco e rebusca tudo")
    parser.add_argument("--sem-adversarios", action="store_true",
                        help="Pula a expansao de adversarios (profundidade 1)")
    parser.add_argument("--sem-jogadores", action="store_true",
                        help="Pula lineups/estatisticas de jogadores")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING"])
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    init_db()
    client = SportAPI7Client(refresh=args.refresh,
                             limite_chamadas=args.limite_chamadas)

    totais: dict[str, int] = {}
    eventos_grupo: list[dict] = []
    interrompido = False

    nome_atual: str | None = None
    try:
        for nome in GRUPO_F:
            nome_atual = nome
            print(f"Coletando {nome}...")
            n, eventos = coletar_selecao(
                client, nome, com_jogadores=not args.sem_jogadores
            )
            totais[nome] = n
            eventos_grupo.extend(eventos)

        nome_atual = None
        if not args.sem_adversarios:
            adversarios = sorted(extrair_adversarios(eventos_grupo, GRUPO_F))
            print(f"\nExpandindo {len(adversarios)} adversarios "
                  f"(ultimos {config.OPPONENT_GAMES_LIMIT} jogos de cada)...")
            for adv in adversarios:
                totais[adv] = coletar_adversario(
                    client, adv, config.OPPONENT_GAMES_LIMIT
                )
    except QuotaExceededError as exc:
        interrompido = True
        print(f"\n[!] Coleta interrompida: {exc}")
        print("    Progresso salvo (cache + banco). Rode de novo mais tarde "
              "para continuar de onde parou.")
        if nome_atual:
            # fallback para o time corrente via scraper Sofascore (sem cota)
            print(f"    Tentando fallback Sofascore para {nome_atual}...")
            try:
                totais[nome_atual] = coletar_historico_time(
                    SofascoreScraper(), nome_atual
                )
            except Exception:
                logger.exception("Fallback Sofascore falhou para %s", nome_atual)

    print("\n=== RELATORIO DA COLETA ===")
    for nome, n in sorted(totais.items(), key=lambda x: -x[1]):
        print(f"  {nome:<30}: {n} partidas")
    print(f"  {'TOTAL':<30}: {sum(totais.values())} partidas")
    print(f"\n  Chamadas reais a API : {client.chamadas_api}")
    print(f"  Servidas pelo cache  : {client.chamadas_cache}")
    if interrompido:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Rodar a suite inteira**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add coletar_copa.py preditivo/data/collector.py tests/test_coletar_copa.py
git commit -m "feat: CLI coletar_copa.py — Grupo F + expansao de adversarios"
```

---

### Task 8: MCP, documentação e verificação final

**Files:**
- Create: `.mcp.json`
- Modify: `README.md`

- [ ] **Step 1: Criar `.mcp.json` (chave via variável de ambiente, nunca hardcoded)**

```json
{
  "mcpServers": {
    "sportapi7": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://mcp.rapidapi.com",
        "--header",
        "x-api-host: sportapi7.p.rapidapi.com",
        "--header",
        "x-api-key: ${RAPIDAPI_KEY}"
      ]
    }
  }
}
```

- [ ] **Step 2: Documentar no `README.md`**

Adicionar seção após a seção de configuração da chave Google, com este
conteúdo (os blocos indentados com 4 espaços viram blocos de código cercados
por três crases no README):

    ## Coleta Copa 2026 — Grupo F (SportAPI7)

    Os modelos preditivos são treinados com dados históricos coletados via
    SportAPI7 (RapidAPI, dados Sofascore). Configure a chave no `.env`:

        RAPIDAPI_KEY=sua_chave_do_rapidapi

    E rode a coleta (idempotente — pode rodar várias vezes; o cache em
    `data/cache_api/` evita gastar cota com chamadas repetidas):

        # plano gratuito (~500 chamadas/mes): rode por ciclos
        python coletar_copa.py --limite-chamadas 450

        # plano pago: carga completa
        python coletar_copa.py

    Detalhes da estratégia de dados:
    `docs/superpowers/specs/2026-06-12-sportapi7-grupo-f-design.md`.

- [ ] **Step 3: Verificação final**

Run: `pytest tests/ -v && python -c "from scrapers.sportapi7 import SportAPI7Client; print('ok')"`
Expected: todos os testes PASS + `ok`

- [ ] **Step 4: Commit**

```bash
git add .mcp.json README.md
git commit -m "docs: MCP do SportAPI7 e instrucoes de coleta do Grupo F"
```

---

## Critério de aceite manual (pós-implementação, requer chave válida)

```bash
python coletar_copa.py --limite-chamadas 50 --sem-adversarios
sqlite3 data/preditivo.db "SELECT COUNT(*) FROM partidas; SELECT COUNT(*) FROM estatisticas_jogadores;"
```

Expected: partidas reais do Grupo F no banco; relatório do CLI consistente com
as contagens; segunda execução com o mesmo comando gasta ~0 chamadas reais
(tudo servido pelo cache).
