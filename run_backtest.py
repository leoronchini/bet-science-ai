#!/usr/bin/env python3
"""CLI para backtest dos modelos preditivos."""

import logging
import sys

sys.path.insert(0, ".")

from preditivo.evaluate.backtest import backtest_outcome, backtest_over_btts


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    print("=== BACKTEST OUTCOME ===")
    result = backtest_outcome()
    for k, v in result.items():
        print(f"  {k}: {v}")

    print("\n=== BACKTEST OVER/BTTS ===")
    result = backtest_over_btts()
    if "erro" in result:
        print(f"  {result['erro']}")
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
