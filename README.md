# Football Stats Agent

Agente CLI em Python que automatiza a análise estatística pré-jogo de partidas de futebol. Digite o nome de uma partida e receba um relatório padronizado com forma recente, estatísticas de gols, H2H, artilheiros e predição probabilística.

> **Aviso:** as predições são estimativas estatísticas baseadas em dados históricos — não há garantia de resultado. Este projeto não fornece conselhos de apostas.

## Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium        # opcional — apenas para a fonte 365scores

copy .env.example .env             # Windows (cp no Unix) e preencher a chave
```

Requer Python 3.11+.

## Uso

```bash
python main.py
```

```
Partida (ou "sair"): Flamengo vs Palmeiras
```

Separadores aceitos: `vs`, `vs.`, `v`, `x`, `contra`, `-` (com espaços ao redor). **O primeiro time é tratado como mandante.**

### Exemplo de saída (seção de predição)

```
═══════════════════════════════════════════════════
  PREDICAO  |  Flamengo vs Palmeiras
═══════════════════════════════════════════════════
  xG Esperado      : Flamengo 1.8 | Palmeiras 1.3
  Resultado        : Vitoria Flamengo 52.0% | Empate 24.0% | Palmeiras 24.0%
  Placar Provavel  : 2-1 (18%) | 1-0 (14%) | 2-0 (11%)
  Total de Gols    : Over 2.5 (61.0%) | BTTS (58.0%)
  Artilheiro       : Pedro (FLA) | Endrick (PAL)
═══════════════════════════════════════════════════
Fontes: sofascore, understat | Gerado em: 2026-06-11 14:32
```

## Arquitetura

**Python coleta, Claude analisa.** Os dados vêm de fontes gratuitas via scrapers Python (sem custo de tokens); o Claude é usado apenas para refinar a predição estatística — e o sistema funciona mesmo sem chave de API (predição Poisson pura).

Cadeia de fontes (em ordem de prioridade): Sofascore → Soccerway → 365scores (opcional, Playwright) → fallback Claude web_search. xG real via Understat (apenas Premier League, La Liga, Bundesliga, Serie A e Ligue 1; demais ligas usam estimativa por médias de gols).

## Configuração (.env)

| Variável | Default | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Opcional. Sem ela, predição é Poisson puro |
| `ENABLE_365SCORES` | `true` | `false` dispensa o Playwright |
| `LOG_LEVEL` | `INFO` | `DEBUG` mostra prompts e reasoning |

## Testes

```bash
pytest
```

Os testes não fazem chamadas de rede.

## Limitações conhecidas

- Fontes de dados são não-oficiais e podem mudar ou bloquear sem aviso — por isso a cadeia de fallback.
- Times com nomes ambíguos (ex: "Barcelona" do Equador) podem resolver para o clube errado; confira o nome canônico exibido no relatório.
- Dados não encontrados aparecem como `N/A` — nunca são inventados.

## Documentação

- [PRD.md](PRD.md) — requisitos de produto
- [TECH_SPEC.md](TECH_SPEC.md) — especificação técnica completa
