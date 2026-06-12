"""Dataclasses do dominio. Convencao: campo None = dado nao encontrado (N/A)."""

import json
from dataclasses import dataclass, field
from typing import Optional

import config


@dataclass
class MatchStats:
    """Estatisticas detalhadas de uma partida (cartoes, escanteios, etc)."""

    escanteios_casa: Optional[int] = None
    escanteios_fora: Optional[int] = None
    cartoes_amarelos_casa: Optional[int] = None
    cartoes_amarelos_fora: Optional[int] = None
    cartoes_vermelhos_casa: Optional[int] = None
    cartoes_vermelhos_fora: Optional[int] = None
    posse_casa: Optional[float] = None
    posse_fora: Optional[float] = None
    chutes_gol_casa: Optional[int] = None
    chutes_gol_fora: Optional[int] = None
    faltas_casa: Optional[int] = None
    faltas_fora: Optional[int] = None
    impedimentos_casa: Optional[int] = None
    impedimentos_fora: Optional[int] = None

    @property
    def total_escanteios(self) -> Optional[int]:
        if self.escanteios_casa is not None and self.escanteios_fora is not None:
            return self.escanteios_casa + self.escanteios_fora
        return None

    @property
    def total_cartoes_amarelos(self) -> Optional[int]:
        if self.cartoes_amarelos_casa is not None and self.cartoes_amarelos_fora is not None:
            return self.cartoes_amarelos_casa + self.cartoes_amarelos_fora
        return None

    @property
    def total_cartoes_vermelhos(self) -> Optional[int]:
        if self.cartoes_vermelhos_casa is not None and self.cartoes_vermelhos_fora is not None:
            return self.cartoes_vermelhos_casa + self.cartoes_vermelhos_fora
        return None


@dataclass
class GameResult:
    """Um jogo passado de um time."""

    date: Optional[str]  # ISO "2025-06-01" ou None
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    competition: Optional[str] = None
    stats: Optional[MatchStats] = None

    def outcome_for(self, team: str) -> str:
        """Retorna 'V', 'E' ou 'D' do ponto de vista de `team`."""
        team_lower = team.lower()
        if self.home_score == self.away_score:
            return "E"
        home_won = self.home_score > self.away_score
        is_home = self.home_team.lower() == team_lower
        return "V" if home_won == is_home else "D"

    def compact(self) -> str:
        date = self.date or "?"
        return f"{date} {self.home_team} {self.home_score}-{self.away_score} {self.away_team}"


@dataclass
class GoalStats:
    avg_scored: Optional[float] = None
    avg_conceded: Optional[float] = None
    btts_pct: Optional[float] = None  # 0-100
    over_15_pct: Optional[float] = None
    over_25_pct: Optional[float] = None
    over_35_pct: Optional[float] = None
    clean_sheets_pct: Optional[float] = None


@dataclass
class Scorer:
    name: str
    goals: int
    assists: Optional[int] = None


@dataclass
class TeamData:
    name: str  # nome canonico resolvido
    resolved_id: Optional[str] = None
    recent_games: list[GameResult] = field(default_factory=list)
    goal_stats: GoalStats = field(default_factory=GoalStats)
    home_record: Optional[str] = None  # ex: "6V 2E 2D"
    away_record: Optional[str] = None
    current_streak: Optional[str] = None
    top_scorers: list[Scorer] = field(default_factory=list)
    xg_for: Optional[float] = None
    xg_against: Optional[float] = None

    @property
    def form_string(self) -> str:
        """'VVEDV...' derivado de recent_games (mais recente primeiro)."""
        return "".join(g.outcome_for(self.name) for g in self.recent_games)


@dataclass
class MatchData:
    """Pacote completo entregue ao predictor/agent."""

    home_team: TeamData
    away_team: TeamData
    h2h: list[GameResult] = field(default_factory=list)
    competition: Optional[str] = None
    match_date: Optional[str] = None
    sources_used: list[str] = field(default_factory=list)

    def to_compact_json(self) -> str:
        """Serializacao enxuta p/ enviar ao Claude — omite None, limita listas."""

        def team_block(t: TeamData) -> dict:
            block = {
                "name": t.name,
                "form": t.form_string or None,
                "games": [g.compact() for g in t.recent_games[: config.RECENT_GAMES_LIMIT]],
                "avg_gf": t.goal_stats.avg_scored,
                "avg_ga": t.goal_stats.avg_conceded,
                "btts": t.goal_stats.btts_pct,
                "o15": t.goal_stats.over_15_pct,
                "o25": t.goal_stats.over_25_pct,
                "o35": t.goal_stats.over_35_pct,
                "home_rec": t.home_record,
                "away_rec": t.away_record,
                "streak": t.current_streak,
                "scorers": [f"{s.name} {s.goals}g" for s in t.top_scorers[: config.TOP_SCORERS_LIMIT]],
                "xg_for": t.xg_for,
                "xg_ag": t.xg_against,
            }
            return {k: v for k, v in block.items() if v not in (None, [], "")}

        payload = {
            "home": team_block(self.home_team),
            "away": team_block(self.away_team),
            "h2h": [g.compact() for g in self.h2h[: config.H2H_LIMIT]],
            "competition": self.competition,
            "date": self.match_date,
        }
        payload = {k: v for k, v in payload.items() if v not in (None, [], "")}
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


@dataclass
class ScorePrediction:
    score: str  # "2-1"
    probability: float  # 0-100


@dataclass
class Prediction:
    xg_home: Optional[float]
    xg_away: Optional[float]
    win_home_pct: float
    draw_pct: float
    win_away_pct: float
    top_scores: list[ScorePrediction]
    over_25_pct: Optional[float]
    btts_pct: Optional[float]
    likely_scorers: list[str]
    reasoning_summary: Optional[str] = None  # interno; NAO vai pro relatorio
    # Campos estendidos para NN (cartoes, escanteios)
    cards_total: Optional[float] = None
    cards_home: Optional[float] = None
    cards_away: Optional[float] = None
    corners_total: Optional[float] = None
    corners_home: Optional[float] = None
    corners_away: Optional[float] = None
