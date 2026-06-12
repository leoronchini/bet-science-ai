# PRD — Football Stats Agent

| Campo | Valor |
|---|---|
| Versão | 1.0 — V1 Scope |
| Status | Draft |
| Data | Junho 2025 |
| Plataforma | CLI (Python) |

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Escopo da V1](#2-escopo-da-v1)
3. [Usuários-Alvo](#3-usuários-alvo)
4. [Requisitos Funcionais](#4-requisitos-funcionais)
5. [Formato de Saída](#5-formato-de-saída)
6. [Arquitetura Técnica](#6-arquitetura-técnica)
7. [Requisitos Não-Funcionais](#7-requisitos-não-funcionais)
8. [Regras de Negócio](#8-regras-de-negócio)
9. [Critérios de Aceite](#9-critérios-de-aceite)
10. [Riscos e Mitigações](#10-riscos-e-mitigações)
11. [Milestones](#11-milestones)
12. [Glossário](#12-glossário)

---

## 1. Visão Geral

### 1.1 Problema

Apostadores esportivos dependem de análises pré-jogo para tomar decisões informadas. A coleta manual de estatísticas é dispersa, demorada e suscetível a erros — exige consulta a múltiplas fontes sem garantia de padronização ou completude.

### 1.2 Solução

O Football Stats Agent automatiza a busca, consolidação e apresentação de dados estatísticos relevantes para uma partida específica, entregando um relatório padronizado via terminal em segundos.

### 1.3 Proposta de Valor

- **Velocidade** — relatório completo gerado em uma única execução de CLI
- **Padronização** — formato de saída fixo e previsível, sem variações entre execuções
- **Confiabilidade** — nunca inventa dados; usa `N/A` quando a informação não está disponível
- **Foco** — entrega exclusivamente o que o apostador precisa, sem ruído editorial

### 1.4 Missão

> *Entregar dados estatísticos de futebol precisos e padronizados, sem invenção de fatos, para apoiar decisões de apostas pré-jogo.*

---

## 2. Escopo da V1

### Incluído

- Interface de linha de comando (CLI) interativa
- Busca automatizada de estatísticas para dois times a partir do nome da partida
- Relatório padronizado exibido no terminal
- Dados de: forma recente, gols, desempenho casa/fora, sequências, artilheiros e H2H
- Predição probabilística (xG, placar mais provável, faixa de gols, artilheiro provável)
- Tratamento de dados ausentes com marcação `N/A`

### Fora do Escopo (V1)

- Interface web ou mobile
- Persistência de dados ou histórico de consultas
- Agendamento ou execução periódica automática
- Integração com plataformas de apostas ou análise de odds
- Conselhos diretos de apostas ou recomendações financeiras
- Suporte a múltiplos idiomas na entrada

### Backlog (Versões Futuras)

- **V2** — Persistência, comparação predição vs. resultado real, interface web simples
- **V3** — Integração com APIs pagas (Opta, StatsBomb), modelo ML próprio

---

## 3. Usuários-Alvo

### Persona Principal — Apostador Analítico

| Atributo | Descrição |
|---|---|
| Perfil | Adulto, familiarizado com apostas esportivas, confortável com terminal |
| Motivação | Tomar decisões de aposta baseadas em dados, não intuição |
| Dor principal | Coletar dados de múltiplas fontes manualmente antes de cada jogo |
| Expectativa | Relatório rápido, confiável e sem dados inventados |

### Fluxo do Usuário

1. Executa `python main.py`
2. Digita o nome da partida (ex: `"Flamengo vs Palmeiras"`)
3. Aguarda o agente buscar e consolidar os dados
4. Lê o relatório padronizado no terminal
5. Usa as informações para embasar sua aposta

---

## 4. Requisitos Funcionais

### 4.1 Interface de Entrada

| ID | Requisito | Prioridade |
|---|---|---|
| RF-01 | Aceitar o nome da partida como input de texto livre no terminal | Must Have |
| RF-02 | Interpretar o formato `"Time A vs Time B"` e variações comuns | Must Have |
| RF-03 | Exibir mensagem de progresso durante a coleta de dados | Should Have |
| RF-04 | Tratar entradas inválidas ou ambíguas com mensagem de erro clara | Must Have |

### 4.2 Coleta de Dados

| ID | Requisito | Prioridade |
|---|---|---|
| RF-05 | Buscar forma recente dos últimos 10 jogos de cada time | Must Have |
| RF-06 | Coletar estatísticas de gols: médias, BTTS, over 1.5/2.5/3.5 | Must Have |
| RF-07 | Coletar desempenho separado em casa e fora | Must Have |
| RF-08 | Identificar sequências atuais (streak) de cada time | Must Have |
| RF-09 | Buscar os principais artilheiros de cada time | Must Have |
| RF-10 | Buscar histórico de confrontos diretos (H2H) | Must Have |
| RF-11 | Usar apenas dados reais e atualizados — nunca inventar | Must Have |
| RF-12 | Marcar `N/A` para qualquer dado não encontrado | Must Have |

### 4.3 Geração de Relatório

| ID | Requisito | Prioridade |
|---|---|---|
| RF-13 | Seguir formato fixo e padronizado em todas as execuções | Must Have |
| RF-14 | Incluir predição probabilística com xG estimado | Must Have |
| RF-15 | Incluir placar mais provável e faixa de gols esperada | Must Have |
| RF-16 | Incluir prováveis artilheiros da partida | Must Have |
| RF-17 | Não conter introduções, conclusões ou conselhos de apostas | Must Have |
| RF-18 | Ser exibido diretamente no terminal via stdout | Must Have |

---

## 5. Formato de Saída

### 5.1 Seções do Relatório

O relatório sempre exibe as 8 seções abaixo, nesta ordem, com `N/A` quando dado não está disponível:

| Seção | Conteúdo |
|---|---|
| `PARTIDA` | Nome dos times, competição, data (se disponível) |
| `FORMA RECENTE` | Últimos 10 jogos: V/E/D, percentuais, mais recente primeiro |
| `ESTATÍSTICAS DE GOLS` | Média gols marcados/sofridos, BTTS%, Over 1.5/2.5/3.5% |
| `DESEMPENHO CASA/FORA` | Resultados separados por mando de campo |
| `SEQUÊNCIAS (STREAKS)` | Streak atual de cada time |
| `ARTILHEIROS` | Top 3-5 artilheiros de cada time na temporada |
| `H2H` | Últimos 5-10 confrontos diretos com placares |
| `PREDIÇÃO` | xG estimado, V/E/D%, placar mais provável, faixa de gols, artilheiro provável |

### 5.2 Exemplo — Seção PREDIÇÃO

```
═══════════════════════════════════════════════════
  PREDIÇÃO  |  Flamengo vs Palmeiras
═══════════════════════════════════════════════════
  xG Esperado      : Flamengo 1.8 | Palmeiras 1.3
  Resultado        : Vitória Flamengo 52% | Empate 24% | Palmeiras 24%
  Placar Provável  : 2-1 (18%) | 1-0 (14%) | 2-0 (11%)
  Total de Gols    : Over 2.5 (61%) | BTTS (58%)
  Artilheiro       : Pedro (FLA) | Endrick (PAL)
═══════════════════════════════════════════════════
```

---

## 6. Arquitetura Técnica

### 6.1 Estratégia de Coleta de Dados

A coleta é feita primariamente por Python (scraping/API gratuita), sem custo de tokens. O Claude é acionado apenas para análise e geração do relatório com os dados já estruturados.

```
Python coleta dados brutos  →  Claude analisa e prediz
(grátis, determinístico)        (tokens mínimos)
```

**Redução estimada de tokens: 60–80% por consulta** em relação à abordagem onde o Claude faz as buscas.

### 6.2 Fontes de Dados Gratuitas

| Fonte | Método | Dados Disponíveis | Cobertura | Viabilidade |
|---|---|---|---|---|
| **Sofascore** (API não-oficial) | `requests` → `api.sofascore.com/api/v1/` | Forma, gols, H2H, artilheiros, escalações | Global | ✅ Prioritária |
| **365scores.com** | Playwright (headless browser) | Estatísticas de partida, forma, H2H | Global | ✅ Suportada |
| **Understat.com** | `requests` + parse de JSON em `<script>` | xG real por jogo e por time | Top 5 ligas europeias | ✅ Para ligas europeias |
| **Soccerway.com** | `requests` + BeautifulSoup | Resultados, H2H, forma | Global | ✅ Fallback |
| **Worldfootball.net** | `requests` + BeautifulSoup | Resultados históricos, H2H | Global | ✅ Fallback |
| **fbref.com** | — | Stats avançadas | Global | ❌ Bloqueia scrapers (403) |

**Ordem de prioridade por dado:**

- **Forma recente / H2H / artilheiros** → Sofascore API não-oficial → Soccerway
- **xG** → Understat (ligas europeias) → estimativa do Claude com base em médias de gols
- **Estatísticas de partida ao vivo/detalhadas** → 365scores (Playwright)
- **Fallback geral** → Claude `web_search` se todas as fontes falharem

### 6.3 Stack

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Runtime | Python 3.11+ | Ecossistema maduro para AI agents |
| Agent Framework | Anthropic SDK + `claude-sonnet-4-6` | Análise e predição com tokens mínimos |
| Scraping leve | `requests` + `BeautifulSoup4` | Sofascore API, Soccerway, Worldfootball |
| Scraping JS | `playwright` (headless Chromium) | 365scores (SPA JavaScript) |
| Fallback de busca | Claude `web_search` tool | Dados não encontrados pelas fontes Python |
| CLI | `input()` nativo | Sem dependência extra para V1 |
| Output | `stdout` formatado | Direto, sem libs de UI |
| Env Vars | `python-dotenv` | Gestão segura de `ANTHROPIC_API_KEY` |

### 6.4 Fluxo de Execução

```
Usuário digita partida
        │
        ▼
   parser.py — extrai e normaliza os dois times
        │
        ▼
   scrapers/ — coleta dados em Python (gratuito)
   ├── sofascore.py   → forma, gols, H2H, artilheiros
   ├── understat.py   → xG real (ligas europeias)
   ├── scores365.py   → stats de partida (Playwright)
   └── fallback.py    → Claude web_search se necessário
        │
        ▼
   agent.py — recebe JSON estruturado, analisa e prediz
        │
        ▼
   predictor.py — xG, probabilidades V/E/D, placares
        │
        ▼
   formatter.py — monta o relatório padronizado
        │
        ▼
   stdout — exibe no terminal
```

### 6.5 Estrutura de Arquivos

```
bet-science-ai/
├── main.py                  # Entry point — loop de input e orquestração
├── agent/
│   ├── agent.py             # Definição do agente e system prompt
│   ├── parser.py            # Interpretação do input do usuário
│   ├── predictor.py         # Cálculo de probabilidades e predições
│   └── formatter.py         # Geração do relatório padronizado
├── scrapers/
│   ├── sofascore.py         # Sofascore API não-oficial (prioritária)
│   ├── understat.py         # xG real — top 5 ligas europeias
│   ├── scores365.py         # 365scores via Playwright (headless)
│   ├── soccerway.py         # Fallback — resultados e H2H
│   └── fallback.py          # Claude web_search para dados ausentes
├── .env                     # ANTHROPIC_API_KEY (não versionar)
├── .env.example             # Template de variáveis de ambiente
├── requirements.txt         # Dependências do projeto
└── PRD.md                   # Este documento
```

---

## 7. Requisitos Não-Funcionais

| ID | Categoria | Requisito |
|---|---|---|
| RNF-01 | Performance | Relatório gerado em no máximo 90 segundos (365scores usa Playwright, que adiciona ~20–30s) |
| RNF-02 | Confiabilidade | Dado ausente nunca causa crash — sempre retorna `N/A` |
| RNF-03 | Precisão | Nenhum dado pode ser inventado ou inferido sem base em fonte real |
| RNF-04 | Reprodutibilidade | Formato de saída idêntico em todas as execuções para a mesma seção |
| RNF-05 | Segurança | `ANTHROPIC_API_KEY` nunca exposta em logs ou output |
| RNF-06 | Portabilidade | Executável em Windows, macOS e Linux com Python 3.11+ |
| RNF-07 | Manutenibilidade | Cada responsabilidade em módulo próprio (parser, formatter, predictor) |
| RNF-08 | Observabilidade | Erros de busca logados com `WARNING` — nunca silenciosos |

---

## 8. Regras de Negócio

### Dados

- **RN-01** — Forma recente: últimos 10 jogos na temporada atual ou mais recente disponível
- **RN-02** — H2H: últimos 10 confrontos diretos, independente de temporada
- **RN-03** — BTTS% e médias de gols: calculados sobre os últimos 10 jogos disponíveis
- **RN-04** — Artilheiros: temporada atual ou mais recente com dados disponíveis

### Output

- **RN-05** — Nenhuma seção pode ser omitida — sempre exibir todas, com `N/A` se necessário
- **RN-06** — Proibido introduções editoriais (ex: *"Analisando a partida..."*)
- **RN-07** — Proibido conselhos de apostas diretos (ex: *"Aposte em over 2.5"*)

### Predição

- **RN-08** — `V% + E% + D%` deve sempre somar 100%
- **RN-09** — xG apresentado por time, nunca apenas o total da partida
- **RN-10** — Placar mais provável lista os 3 placares com maior probabilidade estimada
- **RN-11** — Modelo usa no mínimo 3 variáveis: forma recente, média de gols e H2H
- **RN-12** — Sofascore é a fonte prioritária; outras fontes são acionadas somente se Sofascore falhar para aquele dado específico
- **RN-13** — O Claude não deve fazer buscas web se os dados já foram coletados pelo scraper Python — o fallback de `web_search` é último recurso
- **RN-14** — xG via Understat disponível apenas para jogos de Premier League, La Liga, Bundesliga, Serie A e Ligue 1; para demais ligas, xG é estimado pelo Claude com base em médias de gols

---

## 9. Critérios de Aceite

### Must Pass

- [ ] Input `"Flamengo vs Palmeiras"` retorna relatório com todas as 8 seções preenchidas ou com `N/A`
- [ ] Campo BTTS% exibe valor numérico entre 0–100% ou `N/A`, nunca texto livre
- [ ] Seção PREDIÇÃO: `V% + E% + D% = 100%` sempre
- [ ] Dados nunca inventados — toda estatística numérica tem fonte rastreável
- [ ] Execução não falha por dado ausente — fallback `N/A` sempre funciona
- [ ] Formato de saída idêntico em 5 execuções consecutivas para a mesma partida
- [ ] Relatório gerado em até 60 segundos em rede com latência normal
- [ ] `ANTHROPIC_API_KEY` não aparece em nenhum output ou log

### Should Pass

- [ ] Dados de forma recente condizem com jogos dos últimos 60 dias quando verificados manualmente
- [ ] Artilheiros listados condizem com estatísticas oficiais da temporada corrente
- [ ] xG estimado dentro de margem de ±0.5 gols comparado a modelos de referência pública

---

## 10. Riscos e Mitigações

| ID | Risco | Probabilidade | Mitigação |
|---|---|---|---|
| R-01 | Fontes web bloqueiam busca automatizada | Alta | Usar múltiplas fontes; tool use via Claude evita scraping direto |
| R-02 | Dados desatualizados ou incorretos nas fontes | Média | Cruzar múltiplas fontes; marcar `N/A` se houver divergência |
| R-03 | Modelo inventa estatísticas (hallucination) | Média | System prompt rígido proibindo invenção; validação de formato na saída |
| R-04 | Custo elevado de API em uso intenso | Baixa | Otimizar número de chamadas; caching de consultas frequentes em V2 |
| R-05 | Times com nomes ambíguos causando dados errados | Média | Parser confirma os times identificados antes de buscar |
| R-06 | Tempo de resposta acima de 60s em redes lentas | Baixa | Timeout configurável; buscas em paralelo quando possível |

---

## 11. Milestones

| # | Milestone | Entregável | Status |
|---|---|---|---|
| M1 | Setup e Estrutura Base | Repositório, estrutura de pastas, integração Claude API funcionando | Planejado |
| M2 | CLI Funcional | Input de partida, parsing de times, mensagem de progresso | Planejado |
| M3 | Coleta de Dados | Busca automatizada: forma, gols, H2H, artilheiros para ambos os times | Planejado |
| M4 | Formatação do Relatório | Todas as 8 seções no formato fixo, fallback `N/A` funcionando | Planejado |
| M5 | Motor de Predição | xG, probabilidades V/E/D, placares mais prováveis, artilheiro provável | Planejado |
| M6 | Testes e Validação | 10 partidas testadas manualmente, critérios de aceite verificados | Planejado |
| M7 | Release V1 | README completo, `requirements.txt`, `.env.example`, tag `v1.0` | Planejado |

---

## 12. Glossário

| Termo | Definição |
|---|---|
| **xG** | Expected Goals — estima a qualidade das chances de gol com base em histórico de chutes similares |
| **BTTS** | Both Teams To Score — ambos os times marcam na partida |
| **Over X.5** | Total de gols da partida será maior que X.5 |
| **H2H** | Head-to-Head — histórico de confrontos diretos entre os dois times |
| **Streak** | Sequência consecutiva de resultados do mesmo tipo (ex: 4 vitórias seguidas) |
| **N/A** | Not Available — dado não encontrado nas fontes; nunca inventado |
| **Forma Recente** | Sequência dos últimos 10 jogos: V = Vitória, E = Empate, D = Derrota |
| **CLI** | Command Line Interface — interface operada via terminal |
| **Tool Use** | Capacidade do Claude de chamar ferramentas externas (ex: busca web) durante a resposta |
