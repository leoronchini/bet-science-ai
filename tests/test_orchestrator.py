from unittest.mock import MagicMock, patch

from agent.parser import ParsedMatch
from models.match_data import GameResult, GoalStats, Scorer, TeamData
from scrapers import orchestrator
from scrapers.base import BaseScraper


def complete_team(name):
    games = [GameResult(date="2025-06-01", home_team=name, away_team="X",
                        home_score=2, away_score=0)]
    return TeamData(
        name=name, recent_games=games,
        goal_stats=GoalStats(avg_scored=2.0, avg_conceded=0.5),
        current_streak="1 vitoria",
        top_scorers=[Scorer(name="Alguem", goals=5)],
    )


class FakeScraper(BaseScraper):
    def __init__(self, name, team_result):
        self.source_name = name
        self._team_result = team_result
        self.team_calls = 0

    def fetch_team_data(self, team_name):
        self.team_calls += 1
        return self._team_result(team_name) if callable(self._team_result) else self._team_result

    def fetch_h2h(self, home, away):
        return []


def run_collect(scrapers):
    parsed = ParsedMatch(home_team="TimeA", away_team="TimeB")
    with patch.object(orchestrator, "SofascoreScraper", return_value=scrapers[0]), \
         patch.object(orchestrator, "SoccerwayScraper", return_value=scrapers[1]), \
         patch.object(orchestrator.config, "ENABLE_365SCORES", False), \
         patch.object(orchestrator.understat, "fetch_xg", return_value=None), \
         patch.object(orchestrator.enrichment, "enrich", side_effect=lambda m: m), \
         patch.object(orchestrator.fallback, "fill_missing", side_effect=lambda m, _: m) as fb:
        result = orchestrator.collect(parsed)
    return result, fb


def test_primary_success_skips_secondary():
    primary = FakeScraper("sofascore", complete_team)
    secondary = FakeScraper("soccerway", complete_team)
    result, _ = run_collect([primary, secondary])
    assert secondary.team_calls == 0  # RN-12
    assert "sofascore" in result.sources_used
    assert "soccerway" not in result.sources_used


def test_primary_failure_falls_through():
    primary = FakeScraper("sofascore", None)
    secondary = FakeScraper("soccerway", complete_team)
    result, _ = run_collect([primary, secondary])
    assert secondary.team_calls == 2
    assert "soccerway" in result.sources_used
    assert result.home_team.recent_games


def test_all_fail_returns_valid_matchdata_and_calls_fallback_once():
    primary = FakeScraper("sofascore", None)
    secondary = FakeScraper("soccerway", None)
    result, fb = run_collect([primary, secondary])
    assert result.home_team.name == "TimeA"
    assert result.away_team.name == "TimeB"
    assert result.home_team.recent_games == []
    assert fb.call_count == 1  # RN-13: no maximo uma chamada


def test_merge_does_not_overwrite_primary():
    partial = TeamData(name="TimeA", goal_stats=GoalStats(avg_scored=1.7))
    full = complete_team("TimeA")
    orchestrator._merge_team(partial, full)
    assert partial.goal_stats.avg_scored == 1.7  # mantem valor da fonte prioritaria
    assert partial.recent_games  # preenche o que faltava
    assert partial.top_scorers
