#!/usr/bin/env python3
"""Coleta ultimos N jogos de selecoes via Scores365 (API gratuita, sem cota).

Uso:
    python coletar_ultimos_jogos.py
    python coletar_ultimos_jogos.py --selecoes Brazil Argentina --jogos 10
"""

import argparse
import logging
import sys

sys.path.insert(0, ".")

from preditivo.data.database import _conectar, init_db, obter_time_por_nome, upsert_partida, upsert_time
from scrapers.scores365 import Scores365Scraper

logger = logging.getLogger(__name__)

SELECOES_PADRAO = ["Netherlands", "Japan", "Sweden", "Tunisia"]


def _resolver_time(scraper: Scores365Scraper, nome: str) -> int:
    existente = obter_time_por_nome(nome)
    if existente:
        return existente["id"]
    found = scraper.search_team(nome)
    if not found:
        logger.warning("Time nao encontrado no Scores365: %s", nome)
        return upsert_time(nome, nome)
    sf_id, canonical = found
    with _conectar() as conn:
        row = conn.execute(
            "SELECT id FROM times WHERE sofascore_id = ?", (sf_id,)
        ).fetchone()
        if row:
            return row["id"]
    return upsert_time(nome, canonical, sf_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta ultimos jogos de selecoes via Scores365")
    parser.add_argument("--selecoes", nargs="*", default=SELECOES_PADRAO)
    parser.add_argument("--jogos", type=int, default=5, help="Numero de ultimos jogos por selecao")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    init_db()
    scraper = Scores365Scraper()
    totais: dict[str, int] = {}

    for nome in args.selecoes:
        print(f"Buscando {nome}...")
        found = scraper.search_team(nome)
        if not found:
            print(f"  ERRO: {nome} nao encontrado")
            totais[nome] = 0
            continue

        team_id, canonical = found
        time_db_id = upsert_time(nome, canonical, team_id)
        print(f"  ID Scores365={team_id}, canonical={canonical}")

        resultados = scraper._fetch_results(team_id)
        jogos = resultados[:args.jogos]

        contador = 0
        for jogo in jogos:
            casa_id = _resolver_time(scraper, jogo.home_team)
            fora_id = _resolver_time(scraper, jogo.away_team)
            upsert_partida(
                time_casa_id=casa_id, time_fora_id=fora_id,
                data=jogo.date, competicao=jogo.competition,
                gols_casa=jogo.home_score, gols_fora=jogo.away_score,
            )
            contador += 1
            print(f"    {jogo.date} {jogo.home_team} {jogo.home_score}-{jogo.away_score} {jogo.away_team}")

        totais[nome] = contador

    print("\n=== RELATORIO ===")
    for nome, n in sorted(totais.items(), key=lambda x: -x[1]):
        print(f"  {nome:<30}: {n} partidas")
    print(f"  {'TOTAL':<30}: {sum(totais.values())} partidas")


if __name__ == "__main__":
    main()
