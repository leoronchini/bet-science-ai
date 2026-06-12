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

RECENT_GAMES_LIMIT = 10      # RN-01
H2H_LIMIT = 10               # RN-02
TOP_SCORERS_LIMIT = 5

HOME_ADVANTAGE = 1.15        # fator casa aplicado ao lambda do mandante
AWAY_PENALTY = 0.95
DEFAULT_LAMBDA = 1.3         # prior global quando faltam medias de gols
MAX_GOALS_GRID = 6           # matriz de placares 0..6
AI_MAX_ADJUSTMENT = 10.0  # clamp de +-10 p.p. sobre a predicao-base

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

UNDERSTAT_LEAGUES = {"EPL", "La_liga", "Bundesliga", "Serie_A", "Ligue_1"}  # RN-14
