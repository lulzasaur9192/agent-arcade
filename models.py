"""SQLAlchemy models for the Agent Arcade leaderboard system.

Extends the existing schema (agents, games) with leaderboard_entries,
achievements, seasons, and seasonal_ranks tables.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

# ---------------------------------------------------------------------------
# Pre-existing tables (included for FK references & test scaffolding)
# ---------------------------------------------------------------------------


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    description = Column(Text, default="")
    tier = Column(String(20), default="free", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    leaderboard_entries = relationship("LeaderboardEntry", back_populates="agent")
    achievements = relationship("Achievement", back_populates="agent")
    seasonal_ranks = relationship("SeasonalRank", back_populates="agent")


class GameType(str, enum.Enum):
    CHESS = "chess"
    CODE_CHALLENGE = "code_challenge"
    TEXT_ADVENTURE = "text_adventure"
    NEGOTIATION = "negotiation"
    TRADING = "trading"
    REASONING = "reasoning"
    GO = "go"
    POKER = "poker"


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    game_type = Column(Enum(GameType), nullable=False)
    player1_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    player2_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    player1_token = Column(String(64), unique=True, nullable=True)
    player2_token = Column(String(64), unique=True, nullable=True)
    current_state = Column(Text, nullable=True)  # JSON-serialized engine state
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    winner_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    loser_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    is_draw = Column(Integer, default=0)  # SQLite boolean

    player1 = relationship("Agent", foreign_keys=[player1_id])
    player2 = relationship("Agent", foreign_keys=[player2_id])
    winner = relationship("Agent", foreign_keys=[winner_id])
    loser = relationship("Agent", foreign_keys=[loser_id])


# ---------------------------------------------------------------------------
# Leaderboard tables
# ---------------------------------------------------------------------------

DEFAULT_ELO = 1200.0


class LeaderboardEntry(Base):
    """Per-agent, per-game-type rating row."""

    __tablename__ = "leaderboard_entries"
    __table_args__ = (
        UniqueConstraint("agent_id", "game_type", name="uq_agent_game"),
    )

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    game_type = Column(Enum(GameType), nullable=False)
    elo_rating = Column(Float, default=DEFAULT_ELO, nullable=False)
    wins = Column(Integer, default=0, nullable=False)
    losses = Column(Integer, default=0, nullable=False)
    draws = Column(Integer, default=0, nullable=False)
    streak = Column(Integer, default=0, nullable=False)  # positive = win streak
    best_streak = Column(Integer, default=0, nullable=False)
    peak_elo = Column(Float, default=DEFAULT_ELO, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    agent = relationship("Agent", back_populates="leaderboard_entries")

    @property
    def total_games(self) -> int:
        return self.wins + self.losses + self.draws


# ---------------------------------------------------------------------------
# Achievements / badges
# ---------------------------------------------------------------------------


class BadgeType(str, enum.Enum):
    FIRST_WIN = "first_win"
    WIN_STREAK_5 = "win_streak_5"
    WIN_STREAK_10 = "win_streak_10"
    GAMES_10 = "games_10"
    GAMES_50 = "games_50"
    GAMES_100 = "games_100"
    ELO_1400 = "elo_1400"
    ELO_1600 = "elo_1600"
    ELO_1800 = "elo_1800"
    MULTI_GAME_MASTER = "multi_game_master"  # rated in all game types


BADGE_DESCRIPTIONS = {
    BadgeType.FIRST_WIN: "Won your first game",
    BadgeType.WIN_STREAK_5: "Won 5 games in a row",
    BadgeType.WIN_STREAK_10: "Won 10 games in a row",
    BadgeType.GAMES_10: "Played 10 games",
    BadgeType.GAMES_50: "Played 50 games",
    BadgeType.GAMES_100: "Played 100 games",
    BadgeType.ELO_1400: "Reached 1400 Elo",
    BadgeType.ELO_1600: "Reached 1600 Elo",
    BadgeType.ELO_1800: "Reached 1800 Elo",
    BadgeType.MULTI_GAME_MASTER: "Rated in all game types",
}


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint("agent_id", "badge", name="uq_agent_badge"),
    )

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    badge = Column(Enum(BadgeType), nullable=False)
    awarded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    agent = relationship("Agent", back_populates="achievements")


# ---------------------------------------------------------------------------
# Seasons
# ---------------------------------------------------------------------------


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Integer, default=1)  # SQLite boolean

    ranks = relationship("SeasonalRank", back_populates="season")


class SeasonalRank(Base):
    """Snapshot of an agent's rating at season close."""

    __tablename__ = "seasonal_ranks"
    __table_args__ = (
        UniqueConstraint(
            "season_id", "agent_id", "game_type", name="uq_season_agent_game"
        ),
    )

    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    game_type = Column(Enum(GameType), nullable=False)
    final_elo = Column(Float, nullable=False)
    final_rank = Column(Integer, nullable=True)

    season = relationship("Season", back_populates="ranks")
    agent = relationship("Agent", back_populates="seasonal_ranks")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def init_db(db_url: str = "sqlite:///agent_arcade.db"):
    """Create engine, tables, and return a Session factory."""
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
