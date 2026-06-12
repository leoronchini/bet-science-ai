# Integração SportAPI7 — Coleta de Dados Copa 2026 Grupo F

**Data:** 2026-06-12
**Status:** Aprovado
**Branch:** feature/preditivo-nn

## 1. Visão Estratégica

### Objetivo do projeto

Predizer resultados, gols, cartões e escanteios dos jogos da Copa do Mundo 2026,
começando pelo **Grupo F: Holanda, Japão, Suécia e Tunísia**. As predições vêm dos
modelos de ML já existentes em `preditivo/` (resultado, over/BTTS, cartões,
escanteios, placar via LSTM + ensemble).

### Por que esta fase existe

Os modelos NN só são tão bons quanto os dados de treino. Seleções jogam pouco
(~10-15 jogos/ano), então a estratégia de dados é:

1. **Profundidade** — histórico completo disponível das 4 seleções do Grupo F
   (eliminatórias, amistosos, Copas anteriores, Liga das Nações, Copa Asiática/Africana).
2. **Contexto de força relativa** — últimos ~20 jogos de cada adversário que as 4
   seleções enfrentaram (expansão de profundidade 1). Sem isso, o modelo não sabe
   se um 3-0 da Holanda foi contra a França ou contra Gibraltar.
3. **Sinais mais ricos** — além das stats atuais (escanteios, cartões, posse,
   chutes, faltas), coletar **xG / big chances / passes certos** e **estatísticas
   por jogador** (gols, assistências, cartões, minutos, nota). Isso habilita, em
   fase futura, features de "força do elenco escalado" e mercados individuais.

### Fonte de dados

**SportAPI7 (RapidAPI)** vira a fonte primária. É uma API comercial sobre os dados
do Sofascore — **mesmos IDs de times e eventos** que o scraper atual usa, então o
banco e os modelos não precisam de remapeamento. O scraper `SofascoreScraper`
permanece como fallback quando a cota do RapidAPI estourar.

A chave fica em `RAPIDAPI_KEY` no `.env` (nunca commitada). A chave exposta na
conversa de planejamento deve ser **rotacionada** no painel do RapidAPI.

### Roadmap (visão além desta fase)

| Fase | Entrega | Status |
|------|---------|--------|
| 1 (esta) | Cliente SportAPI7 + schema estendido + coleta Grupo F | Em desenvolvimento |
| 2 | Features de xG e jogadores no `preditivo/features/engine.py`; retreino dos modelos | Futuro |
| 3 | Backtest específico de seleções; calibração para o contexto Copa (campo neutro — repensar `HOME_ADVANTAGE`) | Futuro |
| 4 | Expandir para os demais grupos da Copa 2026 | Futuro |

## 2. Decisões de Design

| Decisão | Escolha | Alternativas descartadas |
|---------|---------|--------------------------|
| Consumo da API | Cliente Python no pipeline + MCP só para exploração interativa | Apenas MCP (não reproduzível) |
| Escopo de dados | 4 seleções (histórico completo) + adversários (últimos ~20 jogos, profundidade 1) | Só as 4 seleções (pouco contexto); todas as 48 classificadas (cota/tempo) |
| Relação com scraper atual | SportAPI7 primário, `SofascoreScraper` fallback | Aposentar scraper; fontes paralelas com reconciliação |
| Dados extras | Schema atual + stats de jogadores + xG/avançadas | Escalações/formações táticas (fase futura) |
| Arquitetura | "Scraper irmão" com a interface existente + cache JSON em disco | Módulo independente; ETL com camada raw completa |

## 3. Arquitetura

```
coletar_copa.py (novo CLI)
    │  Grupo F: Holanda, Japão, Suécia, Tunísia
    ▼
scrapers/sportapi7.py (NOVO)          ──► cache JSON em data/cache_api/
    │  mesma interface do SofascoreScraper
    │  fallback: SofascoreScraper em caso de cota esgotada
    ▼
preditivo/data/collector.py (estendido)
    ▼
data/preditivo.db (schema estendido: jogadores, estatisticas_jogadores, xG)
    ▼
preditivo/features → models → predict (inalterados nesta fase)
```

## 4. Componentes

### 4.1 `scrapers/sportapi7.py` (novo)

Classe `SportAPI7Client(BaseScraper)`, `source_name = "sportapi7"`.

- **Base URL:** `https://sportapi7.p.rapidapi.com/api/v1` — mesmos paths da API
  do Sofascore (`/search/all`, `/team/{id}/events/last/{page}`,
  `/event/{id}/statistics`, `/event/{id}/lineups`).
- **Auth:** headers `x-rapidapi-key` (de `config.RAPIDAPI_KEY`) e
  `x-rapidapi-host: sportapi7.p.rapidapi.com`.
- **Interface compatível** com `SofascoreScraper`: `search_team`, `_last_events`
  (com **paginação** — itera páginas até esgotar, diferente do scraper atual que
  lê só a página 0), `fetch_event_statistics`, `enrich_events_with_stats`,
  `fetch_team_data`, `fetch_h2h`.
- **Filtro de seleções:** `search_team` aceita `national=True` para priorizar
  entidades com `national: true` (evita resolver "Japan" para um clube homônimo).
- **Métodos novos:**
  - `fetch_event_statistics` estendido: além das stats atuais, extrai
    `Expected goals`, `Big chances`, `Accurate passes`.
  - `fetch_event_lineups(event_id)` → lista de stats por jogador
    (nome, sofascore_id do jogador, posição, minutos, gols, assistências,
    cartões, chutes, nota Sofascore).
- **Cache em disco:** toda resposta 200 é salva em
  `data/cache_api/<sha1-do-path>.json`. Antes de qualquer chamada, o cliente
  consulta o cache; hit não gasta cota nem rede. Flag `--refresh` ignora o cache.
- **Rate limiting:** pausa configurável entre chamadas
  (`config.SPORTAPI7_DELAY`, default 0.6s) + contador de chamadas da sessão.
- **Tratamento de erros:**
  - 429 → backoff exponencial (3 tentativas); persistindo, levanta
    `QuotaExceededError` para o chamador acionar fallback/parada graciosa.
  - 401/403 → `RuntimeError` imediato com mensagem apontando o `.env`.
  - Campo ausente na resposta → `None` (convenção existente do projeto).

### 4.2 Migração de schema (`preditivo/data/schema.sql` + `database.py`)

Colunas novas em `estatisticas_detalhadas` (via `ALTER TABLE` idempotente em
`init_db`, preservando bancos existentes):

```sql
xg_casa REAL, xg_fora REAL,
big_chances_casa INTEGER, big_chances_fora INTEGER,
passes_certos_casa INTEGER, passes_certos_fora INTEGER
```

Tabelas novas:

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
```

`MatchStats` (models/match_data.py) ganha os campos opcionais correspondentes
(`xg_casa`, `xg_fora`, `big_chances_*`, `passes_certos_*`); novo dataclass
`PlayerMatchStats`. `database.py` ganha `upsert_jogador` e
`upsert_stats_jogador`, e `upsert_partida` passa a gravar os campos novos.

### 4.3 `coletar_copa.py` (novo CLI)

```
python coletar_copa.py [--limite-chamadas N] [--refresh] [--sem-adversarios]
```

Fluxo:

1. Resolve as 4 seleções via `search_team(national=True)`; persiste em `times`.
2. Para cada seleção: pagina o histórico completo de eventos finalizados →
   `upsert_partida`.
3. Para cada partida das seleções: statistics (com xG) + lineups (jogadores).
4. Expansão: adversários distintos encontrados → últimos ~20 jogos de cada
   (resultado + statistics; **sem lineups**, para economizar cota).
5. Relatório final: partidas novas, stats enriquecidas, jogadores gravados,
   chamadas de API gastas vs. servidas do cache.

Propriedades: **idempotente** (UNIQUEs do schema + cache) e **retomável** —
`--limite-chamadas N` para graciosamente ao atingir N chamadas reais; a próxima
execução continua de onde parou.

Orçamento estimado da carga inicial: ~1.500–2.500 chamadas. Em plano gratuito
(±500/mês), rodar com `--limite-chamadas 450` por ciclo.

### 4.4 Configuração

- `config.py`: `RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")`,
  `SPORTAPI7_DELAY`, `SPORTAPI7_MAX_RETRIES`, `OPPONENT_GAMES_LIMIT = 20`.
- `.env.example`: linha `RAPIDAPI_KEY=...` documentada.
- `.mcp.json` (novo, commitável): server "sportapi7" via `mcp-remote` com a chave
  interpolada de variável de ambiente — **sem chave hardcoded**.
- `data/cache_api/` adicionado ao `.gitignore`.

## 5. Tratamento de Erros

| Situação | Comportamento |
|----------|---------------|
| 429 / cota esgotada | Backoff (3x); depois `QuotaExceededError` → coleta salva progresso e encerra com instrução de quando rodar de novo; fallback `SofascoreScraper` para o time corrente |
| 401/403 | Falha rápida com mensagem apontando `RAPIDAPI_KEY` no `.env` |
| Stat ausente (jogo antigo sem xG) | Grava `NULL`; nunca aborta o jogo |
| Time não encontrado | Warning + segue (comportamento atual mantido) |
| Resposta não-JSON | `None` + warning (convenção atual mantida) |

## 6. Testes

- `tests/test_sportapi7.py` — parsing com fixtures JSON reais (sem rede):
  busca de time nacional, evento → `GameResult`, statistics → `MatchStats` com xG,
  lineups → `PlayerMatchStats`. Cache: segunda chamada idêntica não toca a rede.
- `tests/test_migracao_schema.py` — banco novo e banco legado (schema antigo)
  migram sem perda; upserts de jogadores idempotentes.
- Critério de aceite manual: `python coletar_copa.py --limite-chamadas 50` popula
  o banco com partidas reais do Grupo F e o relatório bate com o conteúdo do DB.

## 7. Fora de Escopo (fases futuras)

- Usar xG/jogadores como features dos modelos NN (fase 2).
- Escalações/formações táticas e desfalques.
- Ajuste de `HOME_ADVANTAGE` para campo neutro de Copa (fase 3).
- Demais grupos da Copa 2026 (fase 4).
