#!/usr/bin/env python3
"""CLI para treinar todos os modelos preditivos."""

import argparse
import logging
import sys

sys.path.insert(0, ".")

from preditivo.train.pipeline import treinar_todos


def main() -> None:
    parser = argparse.ArgumentParser(description="Treina modelos preditivos NN")
    parser.add_argument(
        "--epochs", type=int, default=100,
        help="Numero maximo de epocas (default: 100)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=32,
        help="Tamanho do batch (default: 32)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
        help="Nivel de log (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    resultados = treinar_todos(epochs=args.epochs, batch_size=args.batch_size)
    print("\n=== RESULTADOS DO TREINAMENTO ===")
    for modelo, val_loss in resultados.items():
        print(f"  {modelo}: val_loss = {val_loss:.4f}")


if __name__ == "__main__":
    main()
