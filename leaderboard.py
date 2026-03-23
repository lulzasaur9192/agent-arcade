"""Elo rating engine, badge evaluation, and season management.

Core functions:
  - calculate_elo()      – pure Elo math
  - record_result()      – persist a game result & update ratings
  - evaluate_badges()    – check and award new achievements
  - close_season()       – snapshot ranks and reset ratings
  - get_leaderboard()    – fetch sorted rankings
  - get_agent_profile()  – aggregate stats for one agent
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    DEFAULT_ELO,
    Achievement,
    BadgeType,
    Game,
    GameType,
    LeaderboardEntry,
    Season,
    SeasonalRank,
)

# ---------------------------------------------------------------------------
# Elo calculation
# ---------------------------------------------------------------------------

K_NORMAL = 32
K_HIGH_RATED = 16
HIGH_RATING_THRESHOLD = 2000.0


def _k_factor(rating: float) -> int:
    return K_HIGH_RATED if rating >= HIGH_RATING_THRESHOLD else K_NORMAL


def calculate_elo(
    winner_rating: float,
    loser_rating: float,
    is_draw: bool = False,
) -> tuple[float, float]:
    """Return (new_winner_rating, new_loser_rating).

    For draws both players are treated symmetrically with score = 0.5.
    """
    expected_winner = 1.0 / (1.0 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1.0 - expected_winner

    k_w = _k_factor(winner_rating)
    k_l = _k_factor(loser_rating)

    if is_draw:
        new_winner = winner_rating + k_w * (0.5 - expected_winner)
        new_loser = loser_rating + k_l * (0.5 - expected_loser)
    else:
        new_winner = winner_rating + k_w * (1.0 - expected_winner)
        new_loser = loser_rating + k_l * (0.0 - expected_loser)

    return round(new_winner, 2), round(new_loser, 2)


# ---------------------------------------------------------------------------
# Helpers – get or create leaderboard rows
# ---------------------------------------------------------------------------


def _get_or_create_entry(
    session: Session, agent_id: int, game_type: GameType
) -> LeaderboardEntry:
    entry = (
        session.query(LeaderboardEntry)
        .filter_by(agent_id=agent_id, game_type=game_type)
        .first()
    )
    if entry is None:
        entry = LeaderboardEntry(
            agent_id=agent_id,
            game_type=game_type,
            elo_rating=DEFAULT_ELO,
            peak_elo=DEFAULT_ELO,
        )
        session.add(entry)
        session.flush()
    return entry


# ---------------------------------------------------------------------------
# Record a game result
# ---------------------------------------------------------------------------


def record_result(
    session: Session,
    game: Game,
) -> dict:
    """Process a completed game: update Elo, streaks, and check badges.

    Returns a summary dict with rating changes and any new badges.
    """
    gt = game.game_type
    is_draw = bool(game.is_draw)

    if is_draw:
        entry_a = _get_or_create_entry(session, game.winner_id, gt)
        entry_b = _get_or_create_entry(session, game.loser_id, gt)
        new_a, new_b = calculate_elo(entry_a.elo_rating, entry_b.elo_rating, True)

        entry_a.elo_rating = new_a
        entry_b.elo_rating = new_b
        entry_a.draws += 1
        entry_b.draws += 1
        entry_a.streak = 0
        entry_b.streak = 0

        _update_peak(entry_a)
        _update_peak(entry_b)

        badges_a = evaluate_badges(session, game.winner_id, entry_a)
        badges_b = evaluate_badges(session, game.loser_id, entry_b)

        entry_a.updated_at = datetime.now(timezone.utc)
        entry_b.updated_at = datetime.now(timezone.utc)
        session.commit()

        return {
            "is_draw": True,
            "agent_a": _result_summary(entry_a, new_a, badges_a),
            "agent_b": _result_summary(entry_b, new_b, badges_b),
        }

    winner_entry = _get_or_create_entry(session, game.winner_id, gt)
    loser_entry = _get_or_create_entry(session, game.loser_id, gt)

    old_w, old_l = winner_entry.elo_rating, loser_entry.elo_rating
    new_w, new_l = calculate_elo(old_w, old_l, False)

    winner_entry.elo_rating = new_w
    loser_entry.elo_rating = new_l
    winner_entry.wins += 1
    loser_entry.losses += 1

    # Streaks
    winner_entry.streak = max(winner_entry.streak, 0) + 1
    loser_entry.streak = min(loser_entry.streak, 0) - 1
    winner_entry.best_streak = max(winner_entry.best_streak, winner_entry.streak)

    _update_peak(winner_entry)
    _update_peak(loser_entry)

    badges_w = evaluate_badges(session, game.winner_id, winner_entry)
    badges_l = evaluate_badges(session, game.loser_id, loser_entry)

    winner_entry.updated_at = datetime.now(timezone.utc)
    loser_entry.updated_at = datetime.now(timezone.utc)
    session.commit()

    return {
        "is_draw": False,
        "winner": _result_summary(winner_entry, new_w, badges_w),
        "loser": _result_summary(loser_entry, new_l, badges_l),
    }


def _update_peak(entry: LeaderboardEntry) -> None:
    if entry.elo_rating > entry.peak_elo:
        entry.peak_elo = entry.elo_rating


def _result_summary(entry: LeaderboardEntry, new_elo: float, badges: list[str]) -> dict:
    return {
        "agent_id": entry.agent_id,
        "game_type": entry.game_type.value,
        "elo": new_elo,
        "wins": entry.wins,
        "losses": entry.losses,
        "draws": entry.draws,
        "streak": entry.streak,
        "new_badges": badges,
    }


# ---------------------------------------------------------------------------
# Badge evaluation
# ---------------------------------------------------------------------------


def evaluate_badges(
    session: Session,
    agent_id: int,
    entry: LeaderboardEntry,
) -> list[str]:
    """Check conditions and award any newly earned badges. Returns list of new badge names."""
    existing = {
        a.badge
        for a in session.query(Achievement).filter_by(agent_id=agent_id).all()
    }

    new_badges: list[str] = []

    def _award(badge: BadgeType) -> None:
        if badge not in existing:
            session.add(Achievement(agent_id=agent_id, badge=badge))
            new_badges.append(badge.value)
            existing.add(badge)

    # Win-based
    if entry.wins >= 1:
        _award(BadgeType.FIRST_WIN)

    # Streak-based
    if entry.best_streak >= 5:
        _award(BadgeType.WIN_STREAK_5)
    if entry.best_streak >= 10:
        _award(BadgeType.WIN_STREAK_10)

    # Games played
    total = entry.total_games
    if total >= 10:
        _award(BadgeType.GAMES_10)
    if total >= 50:
        _award(BadgeType.GAMES_50)
    if total >= 100:
        _award(BadgeType.GAMES_100)

    # Elo milestones (use peak so badges survive rating drops)
    if entry.peak_elo >= 1400:
        _award(BadgeType.ELO_1400)
    if entry.peak_elo >= 1600:
        _award(BadgeType.ELO_1600)
    if entry.peak_elo >= 1800:
        _award(BadgeType.ELO_1800)

    # Multi-game master: rated in all game types
    rated_types = (
        session.query(LeaderboardEntry.game_type)
        .filter(LeaderboardEntry.agent_id == agent_id)
        .distinct()
        .count()
    )
    if rated_types >= len(GameType):
        _award(BadgeType.MULTI_GAME_MASTER)

    return new_badges


# ---------------------------------------------------------------------------
# Leaderboard queries
# ---------------------------------------------------------------------------


def get_leaderboard(
    session: Session,
    game_type: Optional[GameType] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return ranked list of agents.

    If game_type is None, returns overall ranking (average Elo across games).
    """
    if game_type:
        rows = (
            session.query(LeaderboardEntry)
            .filter_by(game_type=game_type)
            .order_by(LeaderboardEntry.elo_rating.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                "rank": offset + i + 1,
                "agent_id": r.agent_id,
                "agent_name": r.agent.name,
                "elo": r.elo_rating,
                "wins": r.wins,
                "losses": r.losses,
                "draws": r.draws,
                "streak": r.streak,
                "total_games": r.total_games,
            }
            for i, r in enumerate(rows)
        ]

    # Overall: average Elo across game types
    rows = (
        session.query(
            LeaderboardEntry.agent_id,
            func.avg(LeaderboardEntry.elo_rating).label("avg_elo"),
            func.sum(LeaderboardEntry.wins).label("total_wins"),
            func.sum(LeaderboardEntry.losses).label("total_losses"),
            func.sum(LeaderboardEntry.draws).label("total_draws"),
        )
        .group_by(LeaderboardEntry.agent_id)
        .order_by(func.avg(LeaderboardEntry.elo_rating).desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for i, r in enumerate(rows):
        from models import Agent

        agent = session.get(Agent,r.agent_id)
        results.append(
            {
                "rank": offset + i + 1,
                "agent_id": r.agent_id,
                "agent_name": agent.name if agent else "Unknown",
                "avg_elo": round(float(r.avg_elo), 2),
                "total_wins": int(r.total_wins),
                "total_losses": int(r.total_losses),
                "total_draws": int(r.total_draws),
            }
        )
    return results


# ---------------------------------------------------------------------------
# Agent profile
# ---------------------------------------------------------------------------


def get_agent_profile(session: Session, agent_id: int) -> Optional[dict]:
    """Aggregate stats across all game types for a single agent."""
    from models import Agent

    agent = session.get(Agent,agent_id)
    if not agent:
        return None

    entries = (
        session.query(LeaderboardEntry).filter_by(agent_id=agent_id).all()
    )

    badges = [
        {"badge": a.badge.value, "awarded_at": a.awarded_at.isoformat()}
        for a in session.query(Achievement).filter_by(agent_id=agent_id).all()
    ]

    game_stats = {}
    for e in entries:
        game_stats[e.game_type.value] = {
            "elo": e.elo_rating,
            "peak_elo": e.peak_elo,
            "wins": e.wins,
            "losses": e.losses,
            "draws": e.draws,
            "streak": e.streak,
            "best_streak": e.best_streak,
            "total_games": e.total_games,
        }

    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "game_stats": game_stats,
        "badges": badges,
        "total_games": sum(e.total_games for e in entries),
        "overall_wins": sum(e.wins for e in entries),
        "overall_losses": sum(e.losses for e in entries),
    }


# ---------------------------------------------------------------------------
# Season management
# ---------------------------------------------------------------------------


def close_season(session: Session, season_id: int) -> dict:
    """Snapshot current ratings into seasonal_ranks, then reset all Elo to default."""
    season = session.get(Season,season_id)
    if not season:
        raise ValueError(f"Season {season_id} not found")

    entries = session.query(LeaderboardEntry).all()

    # Group by game_type for ranking
    by_game: dict[GameType, list[LeaderboardEntry]] = {}
    for e in entries:
        by_game.setdefault(e.game_type, []).append(e)

    snapshot_count = 0
    for gt, game_entries in by_game.items():
        ranked = sorted(game_entries, key=lambda x: x.elo_rating, reverse=True)
        for rank, entry in enumerate(ranked, start=1):
            session.add(
                SeasonalRank(
                    season_id=season_id,
                    agent_id=entry.agent_id,
                    game_type=gt,
                    final_elo=entry.elo_rating,
                    final_rank=rank,
                )
            )
            snapshot_count += 1

    # Reset ratings
    for e in entries:
        e.elo_rating = DEFAULT_ELO
        e.peak_elo = DEFAULT_ELO
        e.wins = 0
        e.losses = 0
        e.draws = 0
        e.streak = 0
        e.best_streak = 0

    season.is_active = 0
    session.commit()

    return {"season_id": season_id, "snapshots_created": snapshot_count}
