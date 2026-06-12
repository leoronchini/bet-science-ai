import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from models.match_data import MatchStats
from preditivo.data.database import (
    buscar_partidas_sem_stats,
    init_db,
    obter_time_por_nome,
    upsert_partida,
    upsert_time,
)
from scrapers.sofascore import SofascoreScraper, _parse_event

logger = logging.getLogger(__name__)


def coletar_historico_time(
    scraper: SofascoreScraper,
    nome_time: str,
) -> int:
    """Coleta o historico completo de um time e persiste no banco."""
    found = scraper.search_team(nome_time)
    if not found:
        logger.warning("Time nao encontrado: %s", nome_time)
        return 0

    team_id, canonical = found
    upsert_time(nome_time, canonical, team_id)

    events = scraper._last_events(team_id)
    finished = [e for e in events if e.get("status", {}).get("type") == "finished"]
    scraper.enrich_events_with_stats(finished)

    contador = 0
    for event in finished:
        stats_raw = event.get("_stats")
        if not isinstance(stats_raw, MatchStats):
            event.pop("_stats", None)

        jogo = _parse_event(event)
        if not jogo:
            continue

        time_casa_id = _resolver_ou_criar_time(scraper, jogo.home_team)
        time_fora_id = _resolver_ou_criar_time(scraper, jogo.away_team)

        upsert_partida(
            time_casa_id=time_casa_id,
            time_fora_id=time_fora_id,
            data=jogo.date,
            competicao=jogo.competition,
            gols_casa=jogo.home_score,
            gols_fora=jogo.away_score,
            stats=jogo.stats,
        )
        contador += 1

    logger.info("Time %s: %d partidas coletadas", canonical, contador)
    return contador


def _resolver_ou_criar_time(scraper: SofascoreScraper, nome: str) -> int:
    existente = obter_time_por_nome(nome)
    if existente:
        return existente["id"]
    found = scraper.search_team(nome)
    sf_id = found[0] if found else None
    canonical = found[1] if found else nome
    return upsert_time(nome, canonical, sf_id)


def enriquecer_partidas_sem_stats(limite: int = 100) -> int:
    """Busca estatisticas detalhadas para partidas que ainda nao tem."""
    partidas = buscar_partidas_sem_stats(limite)
    if not partidas:
        logger.info("Nenhuma partida pendente de enriquecimento")
        return 0

    scraper = SofascoreScraper()
    contador = 0
    for p in partidas:
        tc = obter_time_por_nome(p["casa_nome"])
        tf = obter_time_por_nome(p["fora_nome"])
        if not tc or not tf:
            continue
        if not tc.get("sofascore_id") or not tf.get("sofascore_id"):
            continue

        events_casa = scraper._last_events(tc["sofascore_id"])
        for event in events_casa:
            if event.get("status", {}).get("type") != "finished":
                continue
            home = event.get("homeTeam", {}).get("name", "").lower()
            away = event.get("awayTeam", {}).get("name", "").lower()
            if home == p["casa_nome"].lower() and away == p["fora_nome"].lower():
                stats = scraper.fetch_event_statistics(event.get("id"))
                if stats:
                    _upsert_stats_partida(p["id"], stats)
                    contador += 1
                break

    logger.info("%d partidas enriquecidas com stats detalhadas", contador)
    return contador


def _upsert_stats_partida(partida_id: int, stats: MatchStats) -> None:
    """Insere ou atualiza estatisticas detalhadas de uma partida."""
    from preditivo.data.database import _conectar

    with _conectar() as conn:
        conn.execute(
            """INSERT INTO estatisticas_detalhadas
               (partida_id, escanteios_casa, escanteios_fora,
                cartoes_amarelos_casa, cartoes_amarelos_fora,
                cartoes_vermelhos_casa, cartoes_vermelhos_fora,
                posse_casa, posse_fora,
                chutes_gol_casa, chutes_gol_fora,
                faltas_casa, faltas_fora,
                impedimentos_casa, impedimentos_fora)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(partida_id) DO UPDATE SET
                   escanteios_casa=excluded.escanteios_casa,
                   escanteios_fora=excluded.escanteios_fora,
                   cartoes_amarelos_casa=excluded.cartoes_amarelos_casa,
                   cartoes_amarelos_fora=excluded.cartoes_amarelos_fora,
                   cartoes_vermelhos_casa=excluded.cartoes_vermelhos_casa,
                   cartoes_vermelhos_fora=excluded.cartoes_vermelhos_fora,
                   posse_casa=excluded.posse_casa, posse_fora=excluded.posse_fora,
                   chutes_gol_casa=excluded.chutes_gol_casa,
                   chutes_gol_fora=excluded.chutes_gol_fora,
                   faltas_casa=excluded.faltas_casa, faltas_fora=excluded.faltas_fora,
                   impedimentos_casa=excluded.impedimentos_casa,
                   impedimentos_fora=excluded.impedimentos_fora""",
            (
                partida_id,
                stats.escanteios_casa, stats.escanteios_fora,
                stats.cartoes_amarelos_casa, stats.cartoes_amarelos_fora,
                stats.cartoes_vermelhos_casa, stats.cartoes_vermelhos_fora,
                stats.posse_casa, stats.posse_fora,
                stats.chutes_gol_casa, stats.chutes_gol_fora,
                stats.faltas_casa, stats.faltas_fora,
                stats.impedimentos_casa, stats.impedimentos_fora,
            ),
        )


def coletar_varios_times(nomes: list[str], max_workers: int = 3) -> dict[str, int]:
    """Coleta historico de multiplos times em paralelo."""
    init_db()
    scraper = SofascoreScraper()
    resultados: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futuros = {
            pool.submit(coletar_historico_time, scraper, nome): nome
            for nome in nomes
        }
        for futuro in as_completed(futuros):
            nome = futuros[futuro]
            try:
                resultados[nome] = futuro.result()
            except Exception as exc:
                logger.error("Falha ao coletar %s: %s", nome, exc)
                resultados[nome] = 0

    return resultados
