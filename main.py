"""Football Stats Agent — CLI de analise estatistica pre-jogo."""

import logging
import sys

import config
from agent import formatter, predictor
from agent.parser import ParseError, parse_match_input
from scrapers import orchestrator

logger = logging.getLogger(__name__)


def setup_console() -> None:
    """Garante UTF-8 no stdout/stderr (Windows usa cp1252 por padrao)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def setup_logging() -> None:
    # stderr para nao poluir o relatorio em stdout
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def run_query(raw: str) -> None:
    try:
        parsed = parse_match_input(raw)
    except ParseError as exc:
        print(exc)
        return

    print(f"Buscando dados de {parsed.home_team} e {parsed.away_team}...")
    try:
        match_data = orchestrator.collect(parsed)
    except TimeoutError:
        logger.warning("Timeout global de coleta atingido")
        print("[Aviso] Coleta parcial por timeout")
        return
    except Exception:
        logger.exception("Falha inesperada na coleta")
        print("Nao foi possivel coletar os dados. Tente novamente.")
        return

    print("Calculando predicao...")
    prediction = predictor.predict(match_data)

    print(formatter.render(match_data, prediction))


def main() -> None:
    setup_console()
    setup_logging()
    if not config.GOOGLE_API_KEY:
        print(
            "[Aviso] GOOGLE_API_KEY nao configurada (.env). "
            "O agente funcionara apenas com a predicao estatistica local.",
            file=sys.stderr,
        )
    print("Football Stats Agent — digite a partida (ex: Flamengo vs Palmeiras)")
    while True:
        try:
            raw = input('Partida (ou "sair"): ').strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if raw.lower() in ("sair", "exit", "quit", "q"):
            break
        if not raw:
            continue
        run_query(raw)


if __name__ == "__main__":
    main()
