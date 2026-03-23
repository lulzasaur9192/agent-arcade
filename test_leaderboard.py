"""Smoke tests for the Agent Arcade leaderboard system.

Uses an in-memory SQLite database so tests are fast and isolated.
"""

import pytest

from models import Agent, Game, GameType, LeaderboardEntry, Season, init_db
from leaderboard import (
    calculate_elo,
    close_season,
    evaluate_badges,
    get_agent_profile,
    get_leaderboard,
    record_result,
)


@pytest.fixture
def session():
    """Provide a fresh in-memory DB session for each test."""
    Session = init_db("sqlite:///:memory:")
    s = Session()
    yield s
    s.close()


@pytest.fixture
def two_agents(session):
    """Create two agents and return their IDs."""
    a1 = Agent(name="AlphaBot")
    a2 = Agent(name="BetaBot")
    session.add_all([a1, a2])
    session.commit()
    return a1.id, a2.id


# ---------------------------------------------------------------------------
# Elo calculation (pure math, no DB)
# ---------------------------------------------------------------------------


class TestEloCalculation:
    def test_equal_ratings_winner_gains(self):
        new_w, new_l = calculate_elo(1200.0, 1200.0)
        assert new_w > 1200.0
        assert new_l < 1200.0

    def test_equal_ratings_symmetric(self):
        new_w, new_l = calculate_elo(1200.0, 1200.0)
        gain = new_w - 1200.0
        loss = 1200.0 - new_l
        assert abs(gain - loss) < 0.01

    def test_upset_yields_larger_gain(self):
        # Low-rated player beats high-rated
        new_w, _ = calculate_elo(1000.0, 1400.0)
        gain_upset = new_w - 1000.0

        new_w2, _ = calculate_elo(1400.0, 1000.0)
        gain_expected = new_w2 - 1400.0

        assert gain_upset > gain_expected

    def test_draw_equal_ratings_no_change(self):
        new_a, new_b = calculate_elo(1200.0, 1200.0, is_draw=True)
        assert abs(new_a - 1200.0) < 0.01
        assert abs(new_b - 1200.0) < 0.01

    def test_draw_unequal_ratings_converge(self):
        new_a, new_b = calculate_elo(1400.0, 1000.0, is_draw=True)
        # Higher-rated player loses points in a draw vs lower-rated
        assert new_a < 1400.0
        assert new_b > 1000.0

    def test_k_factor_reduces_for_high_rated(self):
        # At 2000+, K=16 instead of 32 → smaller changes
        new_w_high, _ = calculate_elo(2100.0, 2100.0)
        gain_high = new_w_high - 2100.0

        new_w_low, _ = calculate_elo(1200.0, 1200.0)
        gain_low = new_w_low - 1200.0

        assert gain_high < gain_low


# ---------------------------------------------------------------------------
# Record result (DB integration)
# ---------------------------------------------------------------------------


class TestRecordResult:
    def test_win_updates_ratings(self, session, two_agents):
        a1, a2 = two_agents
        game = Game(game_type=GameType.CHESS, winner_id=a1, loser_id=a2)
        session.add(game)
        session.commit()

        result = record_result(session, game)

        assert result["is_draw"] is False
        assert result["winner"]["elo"] > 1200.0
        assert result["loser"]["elo"] < 1200.0
        assert result["winner"]["wins"] == 1
        assert result["loser"]["losses"] == 1

    def test_draw_updates_draws(self, session, two_agents):
        a1, a2 = two_agents
        game = Game(
            game_type=GameType.CODE_CHALLENGE,
            winner_id=a1,
            loser_id=a2,
            is_draw=1,
        )
        session.add(game)
        session.commit()

        result = record_result(session, game)

        assert result["is_draw"] is True
        assert result["agent_a"]["draws"] == 1
        assert result["agent_b"]["draws"] == 1

    def test_streak_tracking(self, session, two_agents):
        a1, a2 = two_agents
        for _ in range(3):
            game = Game(game_type=GameType.CHESS, winner_id=a1, loser_id=a2)
            session.add(game)
            session.commit()
            record_result(session, game)

        entry = (
            session.query(LeaderboardEntry)
            .filter_by(agent_id=a1, game_type=GameType.CHESS)
            .first()
        )
        assert entry.streak == 3
        assert entry.best_streak == 3

    def test_streak_resets_on_loss(self, session, two_agents):
        a1, a2 = two_agents
        # a1 wins twice
        for _ in range(2):
            g = Game(game_type=GameType.CHESS, winner_id=a1, loser_id=a2)
            session.add(g)
            session.commit()
            record_result(session, g)

        # a1 loses
        g = Game(game_type=GameType.CHESS, winner_id=a2, loser_id=a1)
        session.add(g)
        session.commit()
        record_result(session, g)

        entry = (
            session.query(LeaderboardEntry)
            .filter_by(agent_id=a1, game_type=GameType.CHESS)
            .first()
        )
        assert entry.streak == -1  # on a losing streak now
        assert entry.best_streak == 2  # preserved from before


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------


class TestBadges:
    def test_first_win_badge(self, session, two_agents):
        a1, a2 = two_agents
        game = Game(game_type=GameType.CHESS, winner_id=a1, loser_id=a2)
        session.add(game)
        session.commit()

        result = record_result(session, game)
        assert "first_win" in result["winner"]["new_badges"]

    def test_no_duplicate_badges(self, session, two_agents):
        a1, a2 = two_agents
        for _ in range(2):
            game = Game(game_type=GameType.CHESS, winner_id=a1, loser_id=a2)
            session.add(game)
            session.commit()
            result = record_result(session, game)

        # Second win should NOT re-award first_win
        assert "first_win" not in result["winner"]["new_badges"]


# ---------------------------------------------------------------------------
# Leaderboard queries
# ---------------------------------------------------------------------------


class TestLeaderboard:
    def test_game_specific_leaderboard(self, session, two_agents):
        a1, a2 = two_agents
        game = Game(game_type=GameType.CHESS, winner_id=a1, loser_id=a2)
        session.add(game)
        session.commit()
        record_result(session, game)

        lb = get_leaderboard(session, game_type=GameType.CHESS)
        assert len(lb) == 2
        assert lb[0]["agent_id"] == a1  # winner should be ranked first
        assert lb[0]["rank"] == 1

    def test_overall_leaderboard(self, session, two_agents):
        a1, a2 = two_agents
        # a1 wins chess, a2 wins code_challenge
        g1 = Game(game_type=GameType.CHESS, winner_id=a1, loser_id=a2)
        g2 = Game(game_type=GameType.CODE_CHALLENGE, winner_id=a2, loser_id=a1)
        session.add_all([g1, g2])
        session.commit()
        record_result(session, g1)
        record_result(session, g2)

        lb = get_leaderboard(session, game_type=None)
        assert len(lb) == 2
        # Both should have same avg Elo (one win, one loss each across types)
        assert abs(lb[0]["avg_elo"] - lb[1]["avg_elo"]) < 1.0


# ---------------------------------------------------------------------------
# Agent profile
# ---------------------------------------------------------------------------


class TestAgentProfile:
    def test_profile_includes_game_stats(self, session, two_agents):
        a1, a2 = two_agents
        game = Game(game_type=GameType.CHESS, winner_id=a1, loser_id=a2)
        session.add(game)
        session.commit()
        record_result(session, game)

        profile = get_agent_profile(session, a1)
        assert profile is not None
        assert profile["agent_name"] == "AlphaBot"
        assert "chess" in profile["game_stats"]
        assert profile["game_stats"]["chess"]["wins"] == 1
        assert len(profile["badges"]) > 0

    def test_nonexistent_agent_returns_none(self, session):
        assert get_agent_profile(session, 9999) is None


# ---------------------------------------------------------------------------
# Seasons
# ---------------------------------------------------------------------------


class TestSeasons:
    def test_close_season_snapshots_and_resets(self, session, two_agents):
        a1, a2 = two_agents
        game = Game(game_type=GameType.CHESS, winner_id=a1, loser_id=a2)
        session.add(game)
        session.commit()
        record_result(session, game)

        # Verify ratings changed before season close
        entry = (
            session.query(LeaderboardEntry)
            .filter_by(agent_id=a1, game_type=GameType.CHESS)
            .first()
        )
        assert entry.elo_rating != 1200.0

        from datetime import datetime, timezone

        season = Season(
            name="Season 1",
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
        )
        session.add(season)
        session.commit()

        result = close_season(session, season.id)
        assert result["snapshots_created"] == 2  # 2 agents × 1 game type

        # Ratings should be reset
        session.expire_all()
        entry = (
            session.query(LeaderboardEntry)
            .filter_by(agent_id=a1, game_type=GameType.CHESS)
            .first()
        )
        assert entry.elo_rating == 1200.0
        assert entry.wins == 0


# ---------------------------------------------------------------------------
# Flask endpoint smoke tests
# ---------------------------------------------------------------------------


class TestFlaskEndpoints:
    @pytest.fixture
    def client(self):
        """Create a Flask test client with in-memory DB."""
        import app as app_module

        app_module.SessionFactory = init_db("sqlite:///:memory:")
        app_module.app.config["TESTING"] = True

        # Seed data
        s = app_module.SessionFactory()
        a1 = Agent(name="TestBot1")
        a2 = Agent(name="TestBot2")
        s.add_all([a1, a2])
        s.commit()
        g = Game(game_type=GameType.CHESS, winner_id=a1.id, loser_id=a2.id)
        s.add(g)
        s.commit()
        s.close()

        with app_module.app.test_client() as c:
            yield c

    def test_complete_game(self, client):
        resp = client.post("/api/games/1/complete")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["is_draw"] is False

    def test_game_not_found(self, client):
        resp = client.post("/api/games/999/complete")
        assert resp.status_code == 404

    def test_overall_leaderboard_endpoint(self, client):
        client.post("/api/games/1/complete")
        resp = client.get("/api/leaderboard")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "rankings" in data

    def test_game_leaderboard_endpoint(self, client):
        client.post("/api/games/1/complete")
        resp = client.get("/api/leaderboard/chess")
        assert resp.status_code == 200

    def test_invalid_game_type(self, client):
        resp = client.get("/api/leaderboard/invalid_game")
        assert resp.status_code == 400

    def test_agent_profile_endpoint(self, client):
        client.post("/api/games/1/complete")
        resp = client.get("/api/agents/1/profile")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["agent_name"] == "TestBot1"

    def test_agent_not_found(self, client):
        resp = client.get("/api/agents/999/profile")
        assert resp.status_code == 404

    def test_create_season(self, client):
        resp = client.post(
            "/api/seasons",
            json={
                "name": "Season 1",
                "start_date": "2026-01-01T00:00:00",
                "end_date": "2026-03-31T23:59:59",
            },
        )
        assert resp.status_code == 201
        assert resp.get_json()["name"] == "Season 1"

    def test_create_season_missing_fields(self, client):
        resp = client.post("/api/seasons", json={"name": "Incomplete"})
        assert resp.status_code == 400
