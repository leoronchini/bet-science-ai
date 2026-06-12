import os

from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = "gemini-3-flash-preview"
GEMINI_MAX_TOKENS = 2000

ENABLE_365SCORES = os.getenv("ENABLE_365SCORES", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

HTTP_TIMEOUT = 15            # segundos por request
SCRAPER_TIMEOUT = 90         # timeout global de coleta (RNF-01)
PLAYWRIGHT_TIMEOUT = 30_000  # ms

RECENT_GAMES_LIMIT = 30      # RN-01 — a API do 365scores retorna ~40 jogos em 1 request
H2H_LIMIT = 10               # RN-02
TOP_SCORERS_LIMIT = 5

HOME_ADVANTAGE = 1.15        # fator casa aplicado ao lambda do mandante
AWAY_PENALTY = 0.95
DEFAULT_LAMBDA = 1.3         # prior global quando faltam medias de gols
MAX_GOALS_GRID = 6           # matriz de placares 0..6
AI_MAX_ADJUSTMENT = 10.0  # clamp de +-10 p.p. sobre a predicao-base

# --- Copa do Mundo 2026 ---
WORLD_CUP_MODE = True        # foco exclusivo: jogos da Copa 2026
WORLD_CUP_NAME = "Copa do Mundo 2026"
# sedes: mando de campo real so existe para as selecoes anfitrias
HOST_NATIONS = {
    "usa", "united states", "estados unidos",
    "mexico", "méxico", "canada", "canadá",
}
KNOCKOUT_STAGES = {
    "mata-mata", "oitavas", "quartas", "semifinal", "final",
    "round of 32", "round of 16", "quarterfinal", "semifinal", "knockout",
}

# --- Dixon-Coles (modelo ajustado por MLE sobre os jogos coletados) ---
DC_TIME_DECAY = 0.0065       # xi/dia — meia-vida ~107 dias (jogos antigos pesam menos)
DC_PSEUDO_GAMES = 3.0        # regularizacao: pseudo-jogos na media (encolhimento)
DC_MIN_GAMES = 8             # minimo de jogos para confiar no ajuste DC
DC_FIT_ITERATIONS = 25
DC_RHO_MIN, DC_RHO_MAX, DC_RHO_STEP = -0.25, 0.25, 0.05
DC_DEFAULT_GAME_AGE_DAYS = 60  # idade assumida quando o jogo nao tem data

# --- Fatores de contexto (cansaco, importancia, desfalques) ---
FATIGUE_SHORT_REST_DAYS = 3   # descanso <= N dias penaliza o ataque
FATIGUE_PENALTY = 0.93
CONGESTION_GAMES_30D = 7      # calendario congestionado: >= N jogos em 30 dias
CONGESTION_PENALTY = 0.96
KNOCKOUT_GOAL_DAMPING = 0.95  # mata-mata: jogos mais cautelosos
ABSENT_SCORER_PENALTY = 0.94  # por artilheiro lesionado/suspenso (max 2)

# --- Odds de mercado ---
MARKET_BLEND_WEIGHT = 0.55    # peso das odds (sem vig) no 1X2 final; modelo = 0.45
ENABLE_ENRICHMENT = os.getenv("ENABLE_ENRICHMENT", "true").lower() == "true"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

UNDERSTAT_LEAGUES = {"EPL", "La_liga", "Bundesliga", "Serie_A", "Ligue_1"}  # RN-14
