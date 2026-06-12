#!/usr/bin/env python3
"""CLI para coleta de dados historicos."""

import argparse
import logging
import sys

sys.path.insert(0, ".")

from preditivo.data.database import init_db
from preditivo.data.collector import coletar_varios_times, enriquecer_partidas_sem_stats

logger = logging.getLogger(__name__)

TIMES_SUGERIDOS = [
    "Flamengo", "Palmeiras", "Santos", "Sao Paulo", "Corinthians",
    "Gremio", "Internacional", "Cruzeiro", "Atletico Mineiro", "Botafogo",
    "Fluminense", "Vasco", "Bahia", "Fortaleza", "Athletico Paranaense",
    "Red Bull Bragantino", "Cuiaba", "Juventude", "Vitoria", "Criciuma",
    "Manchester City", "Manchester United", "Liverpool", "Arsenal", "Chelsea",
    "Tottenham", "Barcelona", "Real Madrid", "Atletico Madrid",
    "Bayern Munich", "Borussia Dortmund", "Paris Saint Germain",
    "Inter", "Milan", "Juventus", "Napoli",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta dados historicos para treino")
    parser.add_argument(
        "--times", nargs="*", default=TIMES_SUGERIDOS,
        help="Nomes dos times para coletar (default: lista pre-definida)",
    )
    parser.add_argument(
        "--enriquecer", action="store_true",
        help="Apenas enriquecer partidas sem stats detalhadas",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    init_db()

    if args.enriquecer:
        print("Enriquecendo partidas com estatisticas detalhadas...")
        total = enriquecer_partidas_sem_stats(limite=500)
        print(f"Enriquecidas {total} partidas.")
        return

    print(f"Coletando historico de {len(args.times)} times...")
    resultados = coletar_varios_times(args.times)

    print("\n=== RESULTADOS DA COLETA ===")
    total = 0
    for time, n in sorted(resultados.items(), key=lambda x: -x[1]):
        print(f"  {time:<30}: {n} partidas")
        total += n
    print(f"  {'TOTAL':<30}: {total} partidas")

    if total > 0:
        print("\nEnriquecendo com estatisticas detalhadas...")
        enriquecidas = enriquecer_partidas_sem_stats(limite=total)
        print(f"Enriquecidas {enriquecidas} partidas com cartoes/escanteios.")


if __name__ == "__main__":
    main()
