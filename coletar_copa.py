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
