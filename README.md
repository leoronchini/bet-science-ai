# Football Stats Agent

Agente CLI em Python que automatiza a análise estatística pré-jogo de partidas de futebol. Digite o nome de uma partida e receba um relatório padronizado com forma recente, estatísticas de gols, H2H, artilheiros e predição probabilística.

> **Aviso:** as predições são estimativas estatísticas baseadas em dados históricos — não há garantia de resultado. Este projeto não fornece conselhos de apostas.

---

## 1. Obter a chave do Google AI Studio

1. Acesse **[aistudio.google.com](https://aistudio.google.com)**
2. Clique em **Get API Key → Create API key**
3. Copie a chave gerada (começa com `AIza...`)

---

## 2. Configurar a chave no projeto

Abra o arquivo `.env` na raiz do projeto (se não existir, copie o `.env.example`):

```
GOOGLE_API_KEY=AIza...cole_sua_chave_aqui
```

> O sistema funciona **sem a chave** — coleta dados reais e gera predição por Poisson puro. A chave ativa o refinamento da predição pelo Gemini.

---

## Coleta Copa 2026 — Grupo F (SportAPI7)

Os modelos preditivos são treinados com dados históricos coletados via
SportAPI7 (RapidAPI, dados Sofascore). Configure a chave no `.env`:

```
RAPIDAPI_KEY=sua_chave_do_rapidapi
```

E rode a coleta (idempotente — pode rodar várias vezes; o cache em
`data/cache_api/` evita gastar cota com chamadas repetidas):

```bash
# plano gratuito (~500 chamadas/mes): rode por ciclos
python coletar_copa.py --limite-chamadas 450

# plano pago: carga completa
python coletar_copa.py
```

Detalhes da estratégia de dados:
`docs/superpowers/specs/2026-06-12-sportapi7-grupo-f-design.md`.

---

## 3. Executar

### Opção A — duplo clique (mais fácil)

Dê duplo clique no arquivo **`rodar.bat`** na pasta do projeto.

### Opção B — terminal

```powershell
cd "C:\Users\USER\Documents\projects\bet-science-ai"
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" main.py
```

---

## 4. Usar

Quando o agente iniciar, digite a partida e pressione Enter:

```
Partida (ou "sair"): Flamengo vs Palmeiras
```

Separadores aceitos: `vs`, `vs.`, `v`, `x`, `contra`, `-` (com espaços ao redor).
**O primeiro time é sempre tratado como mandante.**

Para encerrar: digite `sair` ou pressione `Ctrl+C`.

---

## Exemplo de saída

```
═══════════════════════════════════════════════════
  PARTIDA  |  Flamengo vs Palmeiras
═══════════════════════════════════════════════════
  Competicao       : Brasileirão - Série A
  Data             : N/A
═══════════════════════════════════════════════════
  FORMA RECENTE (ultimos 10 jogos)
═══════════════════════════════════════════════════
  Flamengo            : VVDVEDVVEE  (5V 3E 2D — 50% vitorias)
  Palmeiras           : VVVDEVEVEE  (5V 4E 1D — 50% vitorias)
═══════════════════════════════════════════════════
  PREDICAO  |  Flamengo vs Palmeiras
═══════════════════════════════════════════════════
  xG Esperado      : Flamengo 1.3 | Palmeiras 1.3
  Resultado        : Vitoria Flamengo 36.2% | Empate 26.7% | Palmeiras 37.1%
  Placar Provavel  : 1-1 (13%) | 0-1 (10%) | 1-0 (10%)
  Total de Gols    : Over 2.5 (46.8%) | BTTS (51.9%)
  Artilheiro       : N/A
═══════════════════════════════════════════════════
Fontes: 365scores | Gerado em: 2026-06-11 22:50
```

---

## Configuração avançada (.env)

| Variável | Default | Descrição |
|---|---|---|
| `GOOGLE_API_KEY` | — | Chave do Google AI Studio (Gemini) |
| `ENABLE_365SCORES` | `true` | `false` desativa a fonte 365scores |
| `LOG_LEVEL` | `INFO` | `DEBUG` mostra detalhes internos no terminal |

---

## Arquitetura

**Python coleta, Gemini analisa.** Os dados vêm de fontes gratuitas via scrapers Python; o Gemini refina a predição estatística com uma única chamada de API por consulta.

Cadeia de fontes (ordem de prioridade): **365scores API** → Sofascore → Soccerway → fallback Gemini Search. xG real via Understat (somente Premier League, La Liga, Bundesliga, Serie A e Ligue 1).

---

## Testes

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pytest
```

Os testes não fazem chamadas de rede (49 casos).

---

## Limitações conhecidas

- Fontes de dados são não-oficiais e podem mudar sem aviso — a cadeia de fallback absorve falhas.
- Times com nomes ambíguos (ex: "Barcelona" equatoriano) podem resolver para o clube errado; confira o nome canônico no relatório.
- Artilheiros aparecem como `N/A` quando a fonte não os retorna.
- Dados nunca são inventados — campos sem fonte aparecem como `N/A`.

---

## Documentação

- [PRD.md](PRD.md) — requisitos de produto
- [TECH_SPEC.md](TECH_SPEC.md) — especificação técnica completa
