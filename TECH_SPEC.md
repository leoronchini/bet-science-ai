# PRD Técnico — Football Stats Agent

> Documento de especificação técnica completo para implementação da V1.
> Complementa o [PRD.md](PRD.md) — leia-o primeiro para contexto de produto.

| Campo | Valor |
|---|---|
| Versão | 1.0 |
| Status | Pronto para implementação |
| Linguagem | Python 3.11+ |
| Referência | PRD.md v1.0 |

---

## Sumário

1. [Visão da Arquitetura](#1-visão-da-arquitetura)
2. [Setup do Projeto](#2-setup-do-projeto)
3. [Modelos de Dados](#3-modelos-de-dados)
4. [Especificação dos Módulos](#4-especificação-dos-módulos)
5. [Scrapers — Especificação Detalhada](#5-scrapers--especificação-detalhada)
6. [Integração com Claude API](#6-integração-com-claude-api)
7. [Motor de Predição](#7-motor-de-predição)
8. [Formatador de Relatório](#8-formatador-de-relatório)
9. [Tratamento de Erros e Logging](#9-tratamento-de-erros-e-logging)
10. [Testes](#10-testes)
11. [Ordem de Implementação](#11-ordem-de-implementação)
12. [Checklist de Release](#12-checklist-de-release)

---

## 1. Visão da Arquitetura

### 1.1 Princípio Central

**Python coleta, Claude analisa.** Nenhuma busca web é feita pelo modelo enquanto os scrapers Python conseguirem entregar os dados. O Claude recebe um JSON estruturado e devolve apenas a análise preditiva.

### 1.2 Diagrama de Componentes

```
┌──────────────────────────────────────────────────────────────┐
│                          main.py (CLI)                       │
│  loop de input → orquestração → exibição do relatório        │
└──────┬───────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐    ┌─────────────────────────────────────────┐
│ agent/        │    │ scrapers/                               │
│ parser.py     │───▶│ orchestrator.py (coordena as fontes)    │
│ (normaliza    │    │   ├── sofascore.py     [prioridade 1]   │
│  o input)     │    │   ├── understat.py     [xG, ligas EU]   │
└──────────────┘    │   ├── scores365.py     [Playwright]     │
                    │   ├── soccerway.py     [fallback]       │
                    │   └── fallback.py      [Claude search]  │
                    └──────────────┬──────────────────────────┘
                                   │ MatchData (dataclass)
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │ agent/predictor.py                      │
                    │ Poisson local + Claude p/ refinamento   │
                    └──────────────┬──────────────────────────┘
                                   │ Prediction (dataclass)
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │ agent/formatter.py → stdout             │
                    └─────────────────────────────────────────┘
```

### 1.3 Decisões de Arquitetura (ADRs resumidos)

| # | Decisão | Justificativa |
|---|---|---|
| AD-01 | Dataclasses Python em vez de dicts soltos | Tipagem, validação, `N/A` centralizado via `Optional` |
| AD-02 | Predição base via distribuição de Poisson local | Determinístico, grátis; Claude apenas refina/contextualiza |
| AD-03 | Scrapers retornam `None` por campo, nunca exceção não tratada | Garante RNF-02 (nunca crashar por dado ausente) |
| AD-04 | Playwright opcional (lazy import) | Quem não usa 365scores não precisa instalar Chromium |
| AD-05 | Uma única chamada ao Claude por consulta | Minimiza tokens (objetivo central da arquitetura) |
| AD-06 | Sem cache/persistência na V1 | Escopo do PRD; estrutura preparada para V2 |

---

## 2. Setup do Projeto

### 2.1 Estrutura Completa de Arquivos

```
bet-science-ai/
├── main.py                      # Entry point CLI
├── config.py                    # Constantes e configuração central
├── agent/
│   ├── __init__.py
│   ├── parser.py                # Parse do input do usuário
│   ├── agent.py                 # Cliente Claude + system prompt
│   ├── predictor.py             # Poisson + orquestração da predição
│   └── formatter.py             # Relatório padronizado
├── scrapers/
│   ├── __init__.py
│   ├── base.py                  # Classe abstrata BaseScraper + helpers HTTP
│   ├── orchestrator.py          # Coordena fontes com prioridade e fallback
│   ├── sofascore.py             # API não-oficial Sofascore
│   ├── understat.py             # xG real (top 5 ligas europeias)
│   ├── scores365.py             # 365scores via Playwright
│   ├── soccerway.py             # Fallback HTML scraping
│   └── fallback.py              # Claude web_search (último recurso)
├── models/
│   ├── __init__.py
│   └── match_data.py            # Todas as dataclasses do domínio
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_predictor.py
│   ├── test_formatter.py
│   ├── test_orchestrator.py
│   └── fixtures/
│       ├── sofascore_team_response.json
│       ├── sofascore_h2h_response.json
│       └── understat_team_page.html
├── .env                         # ANTHROPIC_API_KEY (gitignored)
├── .env.example                 # Template
├── .gitignore
├── requirements.txt
├── README.md
├── PRD.md
└── TECH_SPEC.md                 # Este documento
```

### 2.2 requirements.txt

```
anthropic>=0.40.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
python-dotenv>=1.0.0
playwright>=1.40.0          # opcional — apenas para 365scores
pytest>=8.0.0               # dev
responses>=0.25.0           # dev — mock de HTTP nos testes
```

### 2.3 .env.example

```
ANTHROPIC_API_KEY=sk-ant-...
# Opcional — desativa o scraper 365scores (evita dependência do Playwright)
ENABLE_365SCORES=true
# Opcional — nível de log: DEBUG | INFO | WARNING
LOG_LEVEL=INFO
```

### 2.4 .gitignore

```
.env
__pycache__/
*.pyc
.pytest_cache/
venv/
.venv/
```

### 2.5 Comandos de Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | Unix: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium        # somente se ENABLE_365SCORES=true
copy .env.example .env             # e preencher a chave
python main.py
```

### 2.6 config.py

Constantes centrais — **nenhum outro arquivo deve hardcodar esses valores**:

```python
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]   # falha cedo se ausente
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 2000

ENABLE_365SCORES = os.getenv("ENABLE_365SCORES", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

HTTP_TIMEOUT = 15          # segundos por request
SCRAPER_TIMEOUT = 90       # timeout global de coleta (RNF-01)
PLAYWRIGHT_TIMEOUT = 30_000  # ms

RECENT_GAMES_LIMIT = 10    # RN-01
H2H_LIMIT = 10             # RN-02
TOP_SCORERS_LIMIT = 5

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

UNDERSTAT_LEAGUES = {"EPL", "La_liga", "Bundesliga", "Serie_A", "Ligue_1"}  # RN-14
```

---

## 3. Modelos de Dados

Arquivo: `models/match_data.py`. Todas as estruturas que trafegam entre módulos.

**Convenção `N/A`:** todo campo é `Optional`; `None` significa "não encontrado" e o formatter o renderiza como `N/A`. Nenhum módulo pode preencher um campo com valor inventado (RNF-03).

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GameResult:
    """Um jogo passado de um time."""
    date: Optional[str]            # ISO "2025-06-01" ou None
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    competition: Optional[str] = None

    def outcome_for(self, team: str) -> str:
        """Retorna 'V', 'E' ou 'D' do ponto de vista de `team`."""


@dataclass
class GoalStats:
    avg_scored: Optional[float] = None      # média de gols marcados (10 jogos)
    avg_conceded: Optional[float] = None
    btts_pct: Optional[float] = None        # 0-100
    over_15_pct: Optional[float] = None
    over_25_pct: Optional[float] = None
    over_35_pct: Optional[float] = None
    clean_sheets_pct: Optional[float] = None


@dataclass
class Scorer:
    name: str
    goals: int
    assists: Optional[int] = None


@dataclass
class TeamData:
    name: str                                # nome canônico resolvido
    resolved_id: Optional[str] = None        # id na fonte (ex: Sofascore team id)
    recent_games: list[GameResult] = field(default_factory=list)
    goal_stats: GoalStats = field(default_factory=GoalStats)
    home_record: Optional[str] = None        # ex: "6V 2E 2D"
    away_record: Optional[str] = None
    current_streak: Optional[str] = None     # ex: "3 vitórias consecutivas"
    top_scorers: list[Scorer] = field(default_factory=list)
    xg_for: Optional[float] = None           # média xG a favor (Understat)
    xg_against: Optional[float] = None

    @property
    def form_string(self) -> str:
        """'VVEDV...' derivado de recent_games, ou '' se vazio."""


@dataclass
class MatchData:
    """Pacote completo entregue ao predictor/agent."""
    home_team: TeamData
    away_team: TeamData
    h2h: list[GameResult] = field(default_factory=list)
    competition: Optional[str] = None
    match_date: Optional[str] = None
    sources_used: list[str] = field(default_factory=list)   # rastreabilidade RNF-03

    def to_compact_json(self) -> str:
        """Serialização enxuta p/ enviar ao Claude — omite campos None,
        limita listas (RECENT_GAMES_LIMIT, H2H_LIMIT) e usa chaves curtas
        para minimizar tokens."""


@dataclass
class ScorePrediction:
    score: str          # "2-1"
    probability: float  # 0-100


@dataclass
class Prediction:
    xg_home: Optional[float]
    xg_away: Optional[float]
    win_home_pct: float      # win+draw+loss DEVE somar 100 (RN-08)
    draw_pct: float
    win_away_pct: float
    top_scores: list[ScorePrediction]        # 3 itens (RN-10)
    over_25_pct: Optional[float]
    btts_pct: Optional[float]
    likely_scorers: list[str]                # ["Pedro (FLA)", "Endrick (PAL)"]
    reasoning_summary: Optional[str] = None  # 1-2 frases do Claude (interno; NÃO vai pro relatório)
```

---

## 4. Especificação dos Módulos

### 4.1 main.py

**Responsabilidade:** loop de CLI, orquestração de alto nível, mensagens de progresso.

**Fluxo obrigatório:**

```python
def main():
    # 1. setup_logging(LOG_LEVEL)
    # 2. Loop:
    #    - input("Partida (ou 'sair'): ")
    #    - parse_match_input(raw)            → ParsedMatch | ParseError
    #    - print progresso: "Buscando dados de {home}..."
    #    - orchestrator.collect(parsed)      → MatchData   [com timeout 90s]
    #    - print progresso: "Calculando predição..."
    #    - predictor.predict(match_data)     → Prediction
    #    - formatter.render(match_data, prediction) → str
    #    - print(report)
    # 3. KeyboardInterrupt → sai limpo, sem traceback
```

**Regras:**
- RF-03: imprimir progresso por etapa (coleta por time, predição, formatação).
- RF-04: input inválido → mensagem `Entrada inválida. Use o formato: "Time A vs Time B"` e volta ao loop (não encerra).
- Timeout global de coleta: usar `concurrent.futures` com `SCRAPER_TIMEOUT`; ao estourar, seguir com os dados parciais já coletados.
- Nunca imprimir traceback cru para o usuário; logar com `logger.exception` e exibir mensagem amigável.

### 4.2 agent/parser.py

**Responsabilidade:** transformar texto livre em dois nomes de time.

**API:**

```python
@dataclass
class ParsedMatch:
    home_team: str
    away_team: str

class ParseError(Exception): ...

def parse_match_input(raw: str) -> ParsedMatch: ...
```

**Especificação do parsing (RF-02):**

1. Normalizar: `strip()`, colapsar espaços múltiplos.
2. Separadores aceitos (case-insensitive, com regex): ` vs `, ` vs. `, ` v `, ` x `, ` X `, ` - ` (com espaços), ` contra `.
3. Regex sugerida: `re.split(r"\s+(?:vs\.?|v|x|contra|-)\s+", raw, flags=re.IGNORECASE)`.
4. Validar: exatamente 2 partes, cada uma com ≥ 2 caracteres após strip. Caso contrário → `ParseError`.
5. Manter capitalização original do usuário (resolução de nome canônico é responsabilidade do scraper de busca de time).
6. Primeiro time = mandante (convenção documentada no README).

**Testes mínimos:** `"Brasil vs Argentina"`, `"brasil x argentina"`, `"Real Madrid - Barcelona"`, `"São Paulo vs. Atlético-MG"` (hífen interno do nome não pode ser tratado como separador — exigir espaços ao redor do `-`), entradas inválidas: `""`, `"Flamengo"`, `"a vs b vs c"`.

### 4.3 scrapers/base.py

**Responsabilidade:** infra comum a todos os scrapers.

```python
class BaseScraper(ABC):
    source_name: str  # ex: "sofascore" — vai para MatchData.sources_used

    @abstractmethod
    def fetch_team_data(self, team_name: str) -> Optional[TeamData]: ...

    @abstractmethod
    def fetch_h2h(self, home: TeamData, away: TeamData) -> list[GameResult]: ...

def http_get(url: str, *, headers: dict | None = None,
             timeout: int = HTTP_TIMEOUT) -> Optional[requests.Response]:
    """GET com User-Agent padrão, retry 1x com backoff de 2s em 429/5xx,
    retorna None em qualquer falha (logando WARNING). NUNCA propaga exceção."""
```

**Regras transversais:**
- Toda chamada HTTP passa por `http_get` (logging e resiliência centralizados — RNF-08).
- Delay de cortesia: `time.sleep(0.5)` entre requests consecutivos à mesma fonte.
- Scraper que falha em um campo retorna o objeto com aquele campo `None` — nunca aborta a coleta inteira.

### 4.4 scrapers/orchestrator.py

**Responsabilidade:** coordenar fontes com prioridade (RN-12) e fundir resultados.

**API:**

```python
def collect(parsed: ParsedMatch) -> MatchData: ...
```

**Algoritmo:**

1. **Coleta paralela por time** (`ThreadPoolExecutor`, 2 workers): para cada time, executa a cadeia de fontes.
2. **Cadeia por dado** (não por fonte inteira):
   - Sofascore primeiro. Se `TeamData` veio completo → pronto.
   - Para cada campo ainda `None`: tentar Soccerway, depois 365scores (se `ENABLE_365SCORES`).
   - `xg_for/xg_against`: somente Understat, e somente se a liga do time ∈ `UNDERSTAT_LEAGUES` (RN-14). Caso contrário permanece `None` (o predictor estima).
3. **H2H:** Sofascore → Soccerway → 365scores.
4. **Fallback Claude (`fallback.py`):** acionado apenas se, ao final da cadeia, faltarem campos críticos (forma recente OU stats de gols de algum time) — RN-13. Uma única chamada cobrindo todos os campos faltantes de uma vez.
5. **Merge:** nunca sobrescrever campo já preenchido por fonte de maior prioridade.
6. Registrar cada fonte que contribuiu em `sources_used`.
7. Em qualquer cenário, retorna `MatchData` válido (mesmo que majoritariamente `None`).

---

## 5. Scrapers — Especificação Detalhada

### 5.1 scrapers/sofascore.py — prioridade 1

API JSON não-oficial. **Header `User-Agent` de browser é obrigatório** (sem ele, 403).

**Endpoints:**

| Dado | Endpoint |
|---|---|
| Busca de time | `GET https://api.sofascore.com/api/v1/search/all?q={nome}` |
| Últimos jogos | `GET https://api.sofascore.com/api/v1/team/{id}/events/last/0` |
| H2H | `GET https://api.sofascore.com/api/v1/event/{eventId}/h2h/events` |
| Artilheiros | `GET https://api.sofascore.com/api/v1/team/{id}/unique-tournament/{utId}/season/{seasonId}/top-players/overall` |
| Próximo jogo (p/ achar eventId e h2h) | `GET https://api.sofascore.com/api/v1/team/{id}/events/next/0` |

**Implementação:**

1. `search_team(name)` → primeiro resultado com `type == "team"` e esporte futebol; retorna `(team_id, nome_canônico)`. Sem resultado → `None`.
2. `fetch_team_data`:
   - Buscar últimos eventos, filtrar `status.type == "finished"`, pegar os 10 mais recentes → `recent_games`.
   - Derivar localmente (funções puras, testáveis): `goal_stats` (médias, BTTS, overs), `home_record`/`away_record`, `current_streak`. **Cálculo é em Python, não vem da API.**
   - Artilheiros: descobrir `utId`/`seasonId` a partir do último evento do time; se a navegação falhar, deixar `top_scorers = []`.
3. `fetch_h2h`: achar o próximo confronto entre os dois times via `events/next`; se existir, usar o endpoint de H2H do evento; senão, cruzar `recent_games` dos dois times procurando confrontos mútuos.
4. Salvar respostas reais em `tests/fixtures/` durante o desenvolvimento para os testes.

**Riscos:** API pode mudar sem aviso (não documentada). Todo acesso a chave de dict via `.get()` com default — `KeyError` é bug.

### 5.2 scrapers/understat.py — xG real

Understat embute JSON nos `<script>` da página (`var teamsData = JSON.parse('...')`).

**Implementação:**

1. URL: `https://understat.com/team/{TeamName}/{ano}` — nome com underscores (`Manchester_United`). Mapear nome → slug com tentativa direta + tabela de aliases para casos conhecidos.
2. Extrair com regex: `r"var datesData\s*=\s*JSON\.parse\('(.+?)'\)"` — o conteúdo usa escapes `\xNN`; decodificar com `bytes(s, "utf-8").decode("unicode_escape")` antes do `json.loads`.
3. De `datesData` (lista de jogos com `xG`/`xGA`): calcular média de xG a favor/contra dos últimos 10 jogos → `xg_for`, `xg_against`.
4. Só é chamado pelo orchestrator quando a liga ∈ `UNDERSTAT_LEAGUES`. Determinar o ano da temporada: mês ≥ 7 → ano corrente; senão ano anterior.
5. Time não encontrado (404) → retorna `None` silenciosamente (WARNING no log).

### 5.3 scrapers/scores365.py — Playwright

SPA JavaScript — exige browser headless. **Lazy import** do Playwright dentro da função (AD-04).

**Implementação:**

1. Guard inicial: se `not ENABLE_365SCORES` ou import falhar → retornar `None` com WARNING orientando `playwright install chromium`.
2. Fluxo com `sync_playwright`:
   ```python
   browser = p.chromium.launch(headless=True)
   page = browser.new_page(user_agent=USER_AGENT)
   page.goto(f"https://www.365scores.com/pt-br/search?q={team}", timeout=PLAYWRIGHT_TIMEOUT)
   ```
3. Estratégia preferencial: **interceptar as respostas XHR** (`page.on("response", ...)`) filtrando URLs que contenham `allscores.api` ou `webws.365scores.com` — o JSON da API interna é mais estável que seletores CSS.
4. Estratégia secundária: seletores CSS na página do time (forma, últimos jogos). Documentar cada seletor usado em comentário com data, pois quebram com redesigns.
5. Sempre `browser.close()` em `finally`.
6. Papel no sistema: fonte complementar para stats de partida e H2H quando Sofascore/Soccerway falham. É o scraper mais lento (~20–30s) — por isso é o último da cadeia HTML.

### 5.4 scrapers/soccerway.py — fallback HTML

1. Busca: `https://int.soccerway.com/search/?q={nome}` → parsear com BeautifulSoup (`lxml`), pegar primeiro link `/teams/`.
2. Página do time: tabela `table.matches` → últimos resultados (data, adversário, placar, casa/fora).
3. Derivar os mesmos campos calculados do Sofascore (reusar as funções puras de `base.py` ou módulo `scrapers/stats_calc.py` compartilhado — **não duplicar o cálculo**).
4. Artilheiros e xG: fora do alcance desta fonte → deixa `None`.

### 5.5 scrapers/fallback.py — Claude web_search

Último recurso (RN-13). Usa o server tool `web_search` da API Anthropic.

```python
def fill_missing(match_data: MatchData, missing_fields: list[str]) -> MatchData: ...
```

1. Monta um prompt único listando apenas os campos faltantes dos dois times.
2. Chamada com `tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]`.
3. Forçar resposta em JSON (instruir e parsear; em falha de parse, tentar extrair bloco ```json```).
4. System prompt obrigatório: *"Retorne APENAS dados que você encontrou em fontes reais. Para qualquer dado não encontrado, use null. NUNCA estime ou invente valores."* (RF-11).
5. Merge respeitando a regra de não sobrescrever (orchestrator §4.4-5).

---

## 6. Integração com Claude API

### 6.1 agent/agent.py

**Responsabilidade:** única interface com a API Anthropic para a análise (AD-05).

```python
from anthropic import Anthropic

class StatsAgent:
    def __init__(self): self.client = Anthropic()  # lê ANTHROPIC_API_KEY do env

    def analyze(self, match_data: MatchData, base_prediction: Prediction) -> Prediction:
        """Envia dados compactos + predição Poisson; recebe predição refinada.
        Em QUALQUER falha (API down, parse error, timeout), retorna
        base_prediction inalterada — o sistema nunca depende do Claude
        para produzir um relatório."""
```

### 6.2 System Prompt (conteúdo obrigatório)

```
Você é um analista estatístico de futebol. Você recebe:
1. Dados reais coletados (JSON) — forma, gols, H2H, artilheiros, xG quando disponível.
2. Uma predição-base calculada por modelo de Poisson.

Sua tarefa: refinar a predição-base considerando fatores que o Poisson ignora
(momento/streak, H2H, mando de campo, artilheiros disponíveis).

REGRAS INVIOLÁVEIS:
- Use APENAS os dados fornecidos. Não busque nem presuma dados externos.
- Campos null/ausentes: ignore-os; não os substitua por estimativas.
- Ajustes máximos de ±10 pontos percentuais sobre a predição-base.
- win_home_pct + draw_pct + win_away_pct = 100 exatamente.
- Responda APENAS com o JSON no schema fornecido, sem texto adicional.
```

### 6.3 Schema da resposta esperada

```json
{
  "win_home_pct": 52, "draw_pct": 24, "win_away_pct": 24,
  "xg_home": 1.8, "xg_away": 1.3,
  "top_scores": [{"score": "2-1", "probability": 18}, ...],
  "over_25_pct": 61, "btts_pct": 58,
  "likely_scorers": ["Pedro (FLA)", "Endrick (PAL)"],
  "reasoning_summary": "máx 2 frases"
}
```

**Validação pós-resposta (obrigatória em `agent.py`):**
- Parse JSON; falhou → retorna `base_prediction`.
- `win+draw+away` fora de 99.5–100.5 → renormalizar para somar 100 (RN-08).
- Cada percentual ajustado em mais de 10 p.p. vs. base → clampar no limite.
- `likely_scorers` só pode conter nomes presentes em `top_scorers` dos dados — nome desconhecido é descartado (anti-hallucination, RNF-03).

### 6.4 Orçamento de tokens

| Item | Estimativa |
|---|---|
| System prompt | ~250 tokens |
| `to_compact_json()` (dados) | 600–900 tokens |
| Predição-base | ~150 tokens |
| Resposta | ~300 tokens |
| **Total por consulta** | **~1.3k–1.6k tokens** (1 chamada) |

`to_compact_json()` deve: omitir `None`, abreviar chaves (`"hs"`/`"as"` para placares), formatar jogos como strings compactas (`"2025-06-01 FLA 2-1 PAL"`), e nunca exceder os limites de lista do `config.py`.

---

## 7. Motor de Predição

### 7.1 agent/predictor.py

```python
def predict(match_data: MatchData) -> Prediction:
    base = poisson_baseline(match_data)
    return StatsAgent().analyze(match_data, base)   # com fallback p/ base
```

### 7.2 poisson_baseline — algoritmo

1. **λ (gols esperados) por time:**
   - Se `xg_for`/`xg_against` disponíveis (Understat): `λ_home = (xg_for_home + xg_against_away) / 2`, idem invertido para o visitante.
   - Senão: usar `avg_scored`/`avg_conceded` no lugar do xG.
   - **Fator casa:** `λ_home *= 1.15`, `λ_away *= 0.95` (constantes em `config.py`).
   - Dados insuficientes (sem médias de gols de um time): usar prior global `λ = 1.3` e marcar `xg_*` como `None` no resultado.
2. **Matriz de placares:** `P(h, a) = pois(h; λ_home) * pois(a; λ_away)` para `h, a ∈ [0, 6]` (usar `math.exp/factorial` — não precisa de scipy).
3. **Agregações:**
   - `win_home_pct = Σ P(h>a)`, `draw_pct = Σ P(h==a)`, `win_away_pct = Σ P(h<a)` → ×100, arredondar e **ajustar o maior valor para fechar soma 100**.
   - `top_scores`: 3 células de maior probabilidade (RN-10).
   - `over_25_pct = Σ P(h+a ≥ 3)`; `btts_pct = Σ P(h≥1 e a≥1)`.
4. **likely_scorers (base):** artilheiro nº 1 de cada time, formato `"Nome (ABREV)"`; sem artilheiros → lista vazia (renderiza `N/A`).

**Propriedade de teste crítica:** para quaisquer λ válidos, percentuais somam 100 e nenhum é negativo.

---

## 8. Formatador de Relatório

### 8.1 agent/formatter.py

```python
def render(match_data: MatchData, prediction: Prediction) -> str: ...
def fmt(value, suffix="") -> str:
    """None → 'N/A'; float → 1 casa decimal; senão str(value)."""
```

**Regras de renderização:**
- As 8 seções do PRD §5.1, **sempre nesta ordem, sempre todas presentes** (RN-05).
- Template fixo com larguras de coluna constantes — saída byte-idêntica para os mesmos dados (RNF-04). Proibido usar o Claude para formatar.
- Todo valor passa por `fmt()` — é o único ponto que materializa `N/A`.
- Zero texto editorial: sem saudação, sem conclusão, sem conselho (RF-17, RN-06/07). `reasoning_summary` do Claude **não** aparece no relatório (vai só para o log DEBUG).
- Cabeçalho/separadores: linhas `═` com 51 colunas, como no exemplo do PRD §5.2.

### 8.2 Esqueleto do template (ordem e campos exatos)

```
═══ PARTIDA ═══            home vs away | competição | data
═══ FORMA RECENTE ═══      por time: form_string + contagem V-E-D + %
═══ ESTATÍSTICAS DE GOLS ═ por time: avg marcados/sofridos, BTTS%, O1.5/O2.5/O3.5%
═══ DESEMPENHO CASA/FORA ═ home_record do mandante, away_record do visitante
═══ SEQUÊNCIAS ═══         current_streak de cada time
═══ ARTILHEIROS ═══        até 5 por time: "Nome — N gols"
═══ H2H ═══                até 10 linhas: "data | TimeA 2-1 TimeB"
═══ PREDIÇÃO ═══           formato exato do PRD §5.2
```

Rodapé (única exceção de metadado, exigido p/ rastreabilidade RNF-03):
`Fontes: sofascore, understat | Gerado em: 2026-06-11 14:32`

---

## 9. Tratamento de Erros e Logging

### 9.1 Hierarquia de falhas

| Falha | Comportamento |
|---|---|
| Input inválido | Mensagem amigável, volta ao loop (RF-04) |
| Uma fonte HTTP falha | WARNING no log, próxima fonte da cadeia (RNF-08) |
| Todas as fontes falham p/ um campo | Campo `None` → `N/A` no relatório (RNF-02) |
| Claude API falha | Usa predição Poisson pura (silencioso p/ usuário, WARNING no log) |
| Timeout global (90s) | Relatório com dados parciais + linha `[Aviso] Coleta parcial por timeout` |
| `ANTHROPIC_API_KEY` ausente | Erro claro no startup, antes de qualquer input |

### 9.2 Logging

- `logging` stdlib, configurado uma vez em `main.py`: console `stderr` (não polui o relatório em `stdout`).
- Formato: `%(asctime)s %(levelname)s %(name)s: %(message)s`; logger por módulo (`logging.getLogger(__name__)`).
- **Proibido logar:** a API key (RNF-05), o prompt completo em INFO (apenas em DEBUG).
- Obrigatório logar: cada fonte tentada e seu resultado, contagem de tokens da chamada Claude (`response.usage`), tempo total da coleta.

---

## 10. Testes

### 10.1 Estratégia

- **Sem rede nos testes**: HTTP mockado com `responses`; Playwright não roda no CI da V1 (cobrir só o guard de import/flag).
- Fixtures = respostas reais salvas das APIs (anonimizar nada — são dados públicos).

### 10.2 Casos obrigatórios por módulo

**test_parser.py** — todos os separadores do §4.2; hífen interno (`Atlético-MG`); erros (`""`, time único, 3 times).

**test_predictor.py**
- Soma V+E+D = 100 para grade de λ (0.3 a 3.5).
- λ maior do mandante ⇒ `win_home_pct > win_away_pct`.
- `MatchData` totalmente vazio ⇒ não lança exceção, usa prior, `xg` = `None`.
- Clamp de ±10 p.p. sobre resposta simulada do Claude que extrapola.
- `likely_scorers` com nome fora dos dados é filtrado.

**test_formatter.py**
- `MatchData` vazio ⇒ relatório contém as 8 seções e `N/A`, nunca exceção (critério de aceite "fallback N/A").
- Mesmo input ⇒ saída idêntica em chamadas repetidas (RNF-04).
- Relatório não contém as strings proibidas: `"aposte"`, `"recomend"`, `"analisando"` (case-insensitive) — RN-06/07.

**test_orchestrator.py**
- Sofascore ok ⇒ Soccerway não é chamado (RN-12).
- Sofascore falha ⇒ cadeia segue e campo de fonte secundária não sobrescreve o que viesse de primária.
- Todas falham ⇒ `MatchData` válido com `None`s e fallback Claude chamado 1x no máximo (RN-13).

**test_sofascore.py / test_understat.py** — parse das fixtures: contagem de jogos, derivação de form_string, BTTS/overs calculados corretamente contra valores conferidos à mão; decode do `unicode_escape` do Understat.

### 10.3 Validação manual (M6 do PRD)

Roteiro: 10 partidas reais variadas (2 Brasileirão, 2 Premier League c/ Understat, 2 seleções, 2 ligas menores, 2 com nomes ambíguos tipo "Barcelona" equatoriano). Conferir contra os sites-fonte: forma, artilheiros, H2H. Cronometrar (≤ 90s). Verificar os critérios de aceite do PRD §9 um a um.

---

## 11. Ordem de Implementação

Cada fase termina com seus testes passando (`pytest`).

| Fase | Escopo | Depende de | Mapeia p/ milestone |
|---|---|---|---|
| F1 | `config.py`, `models/match_data.py`, `.env.example`, `.gitignore`, `requirements.txt`, setup do venv | — | M1 |
| F2 | `agent/parser.py` + testes | F1 | M2 |
| F3 | `scrapers/base.py` + módulo de cálculo de stats (funções puras: form, BTTS, overs, streak) + testes | F1 | M3 |
| F4 | `scrapers/sofascore.py` + fixtures + testes | F3 | M3 |
| F5 | `scrapers/soccerway.py`, `scrapers/understat.py` + testes | F3 | M3 |
| F6 | `scrapers/orchestrator.py` + testes de prioridade/merge | F4, F5 | M3 |
| F7 | `agent/predictor.py` (Poisson puro) + testes | F1 | M5 |
| F8 | `agent/formatter.py` + testes | F7 | M4 |
| F9 | `main.py` — fluxo ponta a ponta **sem** Claude (Poisson + scrapers) | F2, F6, F7, F8 | M2/M4 |
| F10 | `agent/agent.py` (refinamento Claude) + validações anti-hallucination | F9 | M5 |
| F11 | `scrapers/fallback.py` (web_search) integrado ao orchestrator | F10 | M3 |
| F12 | `scrapers/scores365.py` (Playwright) — **opcional, por último** | F6 | M3 |
| F13 | Validação manual (roteiro §10.3), README, ajustes | F9–F12 | M6/M7 |

> Nota: F9 entrega um produto funcional sem nenhuma chamada de IA. Isso permite validar coleta e formato antes de gastar qualquer token.

---

## 12. Checklist de Release (V1)

- [ ] `pytest` 100% verde, sem chamadas de rede nos testes
- [ ] 10 partidas do roteiro manual validadas (PRD §9)
- [ ] `grep -ri "sk-ant" .` não retorna nada fora de `.env` (RNF-05)
- [ ] `.env` no `.gitignore` e ausente do histórico git
- [ ] Relatório de partida sem nenhum dado disponível renderiza com `N/A` em tudo
- [ ] `ENABLE_365SCORES=false` funciona sem Playwright instalado
- [ ] README cobre: setup, exemplo de uso com output real, convenção mandante/visitante, limitações (xG só ligas EU, fontes não-oficiais)
- [ ] Log de uma consulta mostra fontes usadas e tokens consumidos
- [ ] Tag `v1.0` criada

---

## Apêndice A — Avisos Legais e de Robustez

- **Fontes não-oficiais:** Sofascore/365scores/Soccerway não publicam API pública; endpoints podem mudar ou bloquear a qualquer momento. O design por cadeia de fallback é a mitigação (R-01/R-02 do PRD). Respeitar `robots.txt` quando aplicável e manter volume de requests baixo (uso pessoal, 1 consulta por vez).
- **Predições ≠ garantia:** RN-11 do PRD — o sistema apresenta estimativas estatísticas; o README deve declarar isso explicitamente.
- **Nomes ambíguos (R-05):** quando a busca de time retornar múltiplos candidatos com esportes/países distintos, exibir no relatório o nome canônico resolvido (ex: `Barcelona (Espanha)`) para o usuário detectar resolução errada.
