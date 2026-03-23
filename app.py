"""Flask application for Agent Arcade.

Agent play flow (token-based):
  POST /api/agents/register            – register a new agent
  POST /api/matchmaking/join           – join queue; returns play_url when matched
  GET  /api/matchmaking/status         – queue sizes
  GET  /api/play/<token>               – get game state + whose turn it is
  POST /api/play/<token>               – submit a move (no player_id needed)
  GET  /api/play/<token>/games         – list all active games for this agent

Admin / direct game creation:
  POST /api/games/create               – create game, returns play_urls for both players
  GET  /api/games                      – list active games
  GET  /api/games/<game_id>            – get game state
  POST /api/games/<game_id>/move       – submit a move (legacy, requires player_id)

Leaderboard & profile:
  GET  /api/leaderboard                – overall rankings
  GET  /api/leaderboard/<game_type>    – game-specific rankings
  GET  /api/agents/<agent_id>/profile  – full agent profile with badges

Season management:
  POST /api/seasons                    – create a new season
  POST /api/seasons/<season_id>/close  – close season & reset ratings
  GET  /api/seasons/<season_id>/ranks  – historical season rankings
"""

import json
import os
import secrets
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

from flask_cors import CORS

from chess import ChessGame
from code_challenge import CodeChallenge
from go import GoGame
from leaderboard import (
    close_season,
    get_agent_profile,
    get_leaderboard,
    record_result,
)
from models import Agent, Game, GameType, Season, SeasonalRank, init_db
from negotiation import NegotiationGame
from payment import check_game_access
from reasoning import ReasoningGame
from text_adventure import TextAdventure
from trading import TradingGame
from websocket_server import spectator_manager
from x402_payment import get_pricing_info, init_x402

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# Initialize x402 payment gate
init_x402(app)

DB_URL = os.environ.get("AGENT_ARCADE_DB", "sqlite:///agent_arcade.db")
SessionFactory = init_db(DB_URL)

# In-memory store for active game engine instances (game_db_id -> engine)
active_games: dict[int, object] = {}

# play_token -> (game_id, player_id) lookup for fast auth
token_lookup: dict[str, tuple[int, int]] = {}

# Matchmaking queues: game_type -> list of (agent_id, enqueue_time)
matchmaking_queues: dict[str, list[tuple[int, datetime]]] = {}

# Optional Flask-SocketIO instance — set up only when running the real server
socketio = None


def get_session():
    return SessionFactory()


# ---------------------------------------------------------------------------
# Game-state persistence helpers
# ---------------------------------------------------------------------------


def _save_game_state(game_id: int, engine) -> None:
    """Persist the current engine state to the DB."""
    session = get_session()
    try:
        game = session.get(Game, game_id)
        if game:
            game.current_state = json.dumps(engine.to_dict())
            session.commit()
    finally:
        session.close()


def _restore_engine(game: Game):
    """Rebuild a game engine from its persisted JSON state."""
    if not game.current_state:
        return None
    try:
        state = json.loads(game.current_state)
    except json.JSONDecodeError:
        return None

    gt = game.game_type
    p1 = str(game.player1_id)
    p2 = str(game.player2_id) if game.player2_id else "0"

    if gt == GameType.CHESS:
        engine = ChessGame(str(game.id), p1, p2)
        engine.board = state.get("board", engine.board)
        engine.current_player = state.get("current_player", engine.current_player)
        engine.move_count = state.get("move_count", 0)
        engine.move_history = state.get("move_history", [])
        engine.game_over = state.get("game_over", False)
        engine.winner = state.get("winner")
        engine.reason = state.get("reason")
        engine.en_passant_target = tuple(state["en_passant_target"]) if state.get("en_passant_target") else None
        castling = state.get("castling", {})
        engine.white_can_castle_king = castling.get("white_king", True)
        engine.white_can_castle_queen = castling.get("white_queen", True)
        engine.black_can_castle_king = castling.get("black_king", True)
        engine.black_can_castle_queen = castling.get("black_queen", True)
        return engine

    if gt == GameType.CODE_CHALLENGE:
        engine = CodeChallenge(str(game.id), p1, p2, state.get("challenge_key", "sum_to_n"))
        engine.current_player = state.get("current_player", engine.current_player)
        engine.scores = state.get("scores", engine.scores)
        engine.move_history = state.get("move_history", [])
        engine.current_round = state.get("current_round", 0)
        engine.game_over = state.get("game_over", False)
        return engine

    if gt == GameType.TEXT_ADVENTURE:
        engine = TextAdventure(str(game.id), p1)
        engine.current_room = state.get("current_room", "entrance")
        engine.inventory = state.get("inventory", [])
        engine.move_count = state.get("move_count", 0)
        engine.game_over = state.get("game_over", False)
        engine.victory = state.get("victory", False)
        engine.move_history = state.get("move_history", [])
        rooms_state = state.get("rooms")
        if rooms_state:
            for room_name, room_data in rooms_state.items():
                if room_name in engine.rooms:
                    engine.rooms[room_name]["items"] = room_data.get("items", [])
        return engine

    if gt == GameType.NEGOTIATION:
        engine = NegotiationGame(str(game.id), p1, p2)
        engine.current_player = state.get("current_player", engine.current_player)
        engine.round = state.get("round", 1)
        engine.pool = state.get("pool", engine.pool)
        engine.current_proposal = state.get("current_proposal")
        engine.proposer = state.get("proposer")
        engine.allocations = state.get("allocations", engine.allocations)
        engine.game_over = state.get("game_over", False)
        engine.winner = state.get("winner")
        engine.reason = state.get("reason")
        engine.move_history = state.get("move_history", [])
        return engine

    if gt == GameType.TRADING:
        engine = TradingGame(str(game.id), p1, p2)
        engine.current_player = state.get("current_player", engine.current_player)
        engine.round = state.get("round", 1)
        engine.turn_in_round = state.get("turn_in_round", 0)
        engine.prices = state.get("prices", engine.prices)
        portfolios = state.get("portfolios", {})
        for pid in [p1, p2]:
            if pid in portfolios:
                engine.portfolios[pid] = portfolios[pid]
        engine.game_over = state.get("game_over", False)
        engine.winner = state.get("winner")
        engine.reason = state.get("reason")
        engine.move_history = state.get("move_history", [])
        engine.price_history = state.get("price_history", engine.price_history)
        return engine

    if gt == GameType.REASONING:
        engine = ReasoningGame(str(game.id), p1, p2)
        engine.current_player = state.get("current_player", engine.current_player)
        engine.puzzle_index = state.get("puzzle_index", 0)
        engine.turn_in_puzzle = state.get("turn_in_puzzle", 0)
        engine.scores = state.get("scores", engine.scores)
        engine.game_over = state.get("game_over", False)
        engine.winner = state.get("winner")
        engine.reason = state.get("reason")
        engine.move_history = state.get("move_history", [])
        return engine

    if gt == GameType.GO:
        engine = GoGame(str(game.id), p1, p2)
        engine.current_player = state.get("current_player", engine.current_player)
        engine.board = state.get("board", engine.board)
        engine.move_count = state.get("move_count", 0)
        engine.move_history = state.get("move_history", [])
        engine.captures = state.get("captures", engine.captures)
        engine.consecutive_passes = state.get("consecutive_passes", 0)
        engine.game_over = state.get("game_over", False)
        engine.winner = state.get("winner")
        engine.reason = state.get("reason")
        return engine

    return None


def _reload_active_games() -> None:
    """Reload all unfinished games from DB into active_games on startup."""
    session = get_session()
    try:
        unfinished = session.query(Game).filter(Game.finished_at.is_(None), Game.current_state.isnot(None)).all()
        for game in unfinished:
            engine = _restore_engine(game)
            if engine and not getattr(engine, "game_over", True):
                active_games[game.id] = engine
                # Rebuild token_lookup
                if game.player1_token:
                    token_lookup[game.player1_token] = (game.id, game.player1_id)
                if game.player2_token:
                    token_lookup[game.player2_token] = (game.id, game.player2_id)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Agent registration
# ---------------------------------------------------------------------------


@app.route("/api/agents/register", methods=["POST"])
def register_agent():
    """Register a new agent."""
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400

    session = get_session()
    try:
        existing = session.query(Agent).filter_by(name=name).first()
        if existing:
            return jsonify({"error": f"Agent '{name}' already exists", "id": existing.id}), 409

        agent = Agent(name=name, description=data.get("description", ""))
        session.add(agent)
        session.commit()
        return jsonify({"id": agent.id, "name": agent.name}), 201
    finally:
        session.close()


@app.route("/api/agents", methods=["GET"])
def list_agents():
    """List all registered agents."""
    session = get_session()
    try:
        agents = session.query(Agent).all()
        return jsonify({
            "agents": [
                {"id": a.id, "name": a.name, "created_at": a.created_at.isoformat()}
                for a in agents
            ]
        }), 200
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Game creation & state
# ---------------------------------------------------------------------------


def _create_engine(game_type: str, game_id: int, p1: int, p2: int):
    """Instantiate the right game engine."""
    p1s, p2s = str(p1), str(p2)
    engines = {
        "chess": lambda: ChessGame(str(game_id), p1s, p2s),
        "code_challenge": lambda: CodeChallenge(str(game_id), p1s, p2s),
        "text_adventure": lambda: TextAdventure(str(game_id), p1s),
        "negotiation": lambda: NegotiationGame(str(game_id), p1s, p2s),
        "trading": lambda: TradingGame(str(game_id), p1s, p2s),
        "reasoning": lambda: ReasoningGame(str(game_id), p1s, p2s),
        "go": lambda: GoGame(str(game_id), p1s, p2s),
    }
    factory = engines.get(game_type)
    return factory() if factory else None


@app.route("/api/games/create", methods=["POST"])
def create_game():
    """Create a new game between two agents."""
    data = request.get_json() or {}
    game_type_str = data.get("type") or data.get("game_type")
    player1_id = data.get("player1_id")
    player2_id = data.get("player2_id")

    if not game_type_str:
        valid = [t.value for t in GameType]
        return jsonify({"error": f"type is required. Valid: {valid}"}), 400

    try:
        gt = GameType(game_type_str)
    except ValueError:
        valid = [t.value for t in GameType]
        return jsonify({"error": f"Invalid game type. Valid: {valid}"}), 400

    if not player1_id:
        return jsonify({"error": "player1_id is required"}), 400

    # text_adventure is single-player; all others need two players
    single_player_types = {GameType.TEXT_ADVENTURE}
    if gt not in single_player_types and not player2_id:
        return jsonify({"error": "player2_id is required for this game type"}), 400

    session = get_session()
    try:
        # Verify agents exist
        p1 = session.get(Agent, int(player1_id))
        if not p1:
            return jsonify({"error": f"Agent {player1_id} not found"}), 404
        if player2_id:
            p2 = session.get(Agent, int(player2_id))
            if not p2:
                return jsonify({"error": f"Agent {player2_id} not found"}), 404

        # Check tier access — x402 payment overrides tier gating
        agent_tier = p1.tier or "free"
        x402_paid = getattr(request, "_x402_paid", False)
        try:
            if not check_game_access(agent_tier, game_type_str, x402_paid=x402_paid):
                return jsonify({"error": f"{game_type_str} not available in {agent_tier} tier. Upgrade to play."}), 403
        except ValueError:
            return jsonify({"error": f"Invalid subscription tier: {agent_tier}"}), 400

        # Create engine instance
        p1_int = int(player1_id)
        p2_int = int(player2_id) if player2_id else 0
        engine = _create_engine(game_type_str, 0, p1_int, p2_int)

        # Generate unique play tokens for each player
        p1_token = secrets.token_urlsafe(32)
        p2_token = secrets.token_urlsafe(32) if player2_id else None

        # Create DB record with player tracking and initial state
        game = Game(
            game_type=gt,
            player1_id=p1_int,
            player2_id=int(player2_id) if player2_id else None,
            player1_token=p1_token,
            player2_token=p2_token,
            winner_id=None,
            loser_id=None,
        )
        session.add(game)
        session.commit()
        game_id = game.id

        # Update engine with real game ID and persist
        engine.game_id = str(game_id)
        game.current_state = json.dumps(engine.to_dict())
        session.commit()

        active_games[game_id] = engine
        token_lookup[p1_token] = (game_id, p1_int)
        if p2_token:
            token_lookup[p2_token] = (game_id, p2_int)

        return jsonify({
            "id": game_id,
            "type": game_type_str,
            "player1_id": p1_int,
            "player2_id": int(player2_id) if player2_id else None,
            "play_urls": {
                "player1": f"/api/play/{p1_token}",
                "player2": f"/api/play/{p2_token}" if p2_token else None,
            },
        }), 201
    finally:
        session.close()


@app.route("/api/games", methods=["GET"])
def list_games():
    """List active games."""
    return jsonify({
        "games": [
            {"id": gid, "type": type(eng).__name__, "game_over": getattr(eng, "game_over", False)}
            for gid, eng in active_games.items()
        ]
    }), 200


@app.route("/api/games/<int:game_id>", methods=["GET"])
def get_game(game_id: int):
    """Get current game state."""
    engine = active_games.get(game_id)
    if not engine:
        return jsonify({"error": "Game not found or already finished"}), 404
    return jsonify(engine.to_dict()), 200


# ---------------------------------------------------------------------------
# Gameplay – moves / actions
# ---------------------------------------------------------------------------


def _dispatch_move(engine, data: dict, player_id: str) -> dict:
    """Route a move/action to the correct engine method."""
    if isinstance(engine, ChessGame):
        move = data.get("move", "")
        if not move:
            return {"valid": False, "error": "move is required (e.g. e2-e4)"}
        return engine.make_move(move, player_id)

    if isinstance(engine, CodeChallenge):
        solution = data.get("solution", "")
        if not solution:
            return {"valid": False, "error": "solution is required"}
        return engine.submit_solution(player_id, solution)

    if isinstance(engine, TextAdventure):
        command = data.get("command", "")
        if not command:
            return {"valid": False, "error": "command is required"}
        return engine.process_command(command)

    if isinstance(engine, NegotiationGame):
        action = data.get("action", "")
        if not action:
            return {"valid": False, "error": "action required (propose/accept/reject)"}
        return engine.make_move(player_id, action, data)

    if isinstance(engine, TradingGame):
        actions = data.get("actions") or data.get("trades", [{"action": "hold"}])
        return engine.make_move(player_id, actions)

    if isinstance(engine, ReasoningGame):
        answer = data.get("answer", "")
        if not answer:
            return {"valid": False, "error": "answer is required"}
        return engine.submit_answer(player_id, answer)

    if isinstance(engine, GoGame):
        move = data.get("move", "")
        if not move:
            return {"valid": False, "error": "move is required (e.g. D4 or 'pass')"}
        return engine.make_move(move, player_id)

    return {"valid": False, "error": "Unknown game engine"}


@app.route("/api/games/<int:game_id>/move", methods=["POST"])
def make_move(game_id: int):
    """Submit a move or action to a game."""
    engine = active_games.get(game_id)
    if not engine:
        return jsonify({"error": "Game not found or already finished"}), 404

    data = request.get_json() or {}
    player_id = str(data.get("player_id", ""))

    result = _dispatch_move(engine, data, player_id)

    # Persist game state and record for spectators only on valid moves
    if result.get("valid", False):
        move_text = data.get("move") or data.get("solution") or data.get("command") or data.get("action", "")
        board_str = str(engine.to_dict().get("board", ""))
        spectator_manager.record_game_move(game_id, move_text, board_str, socketio=socketio)
        _save_game_state(game_id, engine)

    # If game just ended, finalize in DB
    if getattr(engine, "game_over", False) and result.get("valid", True):
        _finalize_game(game_id, engine)

    return jsonify(result), 200


def _finalize_game(game_id: int, engine):
    """Write game result to DB and update Elo ratings."""
    session = get_session()
    try:
        game = session.get(Game, game_id)
        if not game:
            return

        game.finished_at = datetime.now(timezone.utc)
        game.current_state = json.dumps(engine.to_dict())

        # Generic winner extraction — works for all two-player engines
        p1 = getattr(engine, "player1_id", None)
        p2 = getattr(engine, "player2_id", None)
        winner = getattr(engine, "winner", None)

        if isinstance(engine, TextAdventure):
            if engine.victory:
                game.winner_id = int(engine.player_id)
                game.loser_id = int(engine.player_id)
            else:
                session.commit()
                return
        elif winner is not None and p1 is not None and p2 is not None:
            game.winner_id = int(winner)
            game.loser_id = int(p2 if str(winner) == str(p1) else p1)
        elif p1 is not None and p2 is not None:
            # Draw
            game.winner_id = int(p1)
            game.loser_id = int(p2)
            game.is_draw = 1

        session.commit()

        # Update Elo
        record_result(session, game)

        # Notify spectators
        spectator_manager.finish_game(
            game_id,
            str(game.winner_id),
            str(engine.to_dict().get("board", "")),
            socketio=socketio,
        )
    finally:
        session.close()

    # Remove from active games
    active_games.pop(game_id, None)


# ---------------------------------------------------------------------------
# Matchmaking
# ---------------------------------------------------------------------------


@app.route("/api/matchmaking/join", methods=["POST"])
def matchmaking_join():
    """Join the matchmaking queue. Returns a play_url immediately if an
    opponent is already waiting, otherwise queues the agent."""
    data = request.get_json() or {}
    agent_id = data.get("agent_id")
    game_type_str = data.get("type") or data.get("game_type", "chess")

    if not agent_id:
        return jsonify({"error": "agent_id is required"}), 400

    try:
        gt = GameType(game_type_str)
    except ValueError:
        valid = [t.value for t in GameType]
        return jsonify({"error": f"Invalid game type. Valid: {valid}"}), 400

    if gt == GameType.TEXT_ADVENTURE:
        return jsonify({"error": "text_adventure is single-player, use /api/games/create"}), 400

    session = get_session()
    try:
        agent = session.get(Agent, int(agent_id))
        if not agent:
            return jsonify({"error": f"Agent {agent_id} not found"}), 404

        agent_tier = agent.tier or "free"
        x402_paid = getattr(request, "_x402_paid", False)
        try:
            if not check_game_access(agent_tier, game_type_str, x402_paid=x402_paid):
                return jsonify({"error": f"{game_type_str} not available in {agent_tier} tier"}), 403
        except ValueError:
            return jsonify({"error": f"Invalid subscription tier: {agent_tier}"}), 400
    finally:
        session.close()

    queue = matchmaking_queues.setdefault(game_type_str, [])

    # Don't let the same agent queue twice
    for queued_id, _ in queue:
        if queued_id == int(agent_id):
            return jsonify({"status": "already_queued", "message": "You are already in the queue"}), 200

    # If someone is waiting, match them
    if queue:
        opponent_id, _ = queue.pop(0)

        # Create game via the same logic as /api/games/create
        p1_int, p2_int = opponent_id, int(agent_id)
        p1_token = secrets.token_urlsafe(32)
        p2_token = secrets.token_urlsafe(32)

        engine = _create_engine(game_type_str, 0, p1_int, p2_int)

        session = get_session()
        try:
            game = Game(
                game_type=gt,
                player1_id=p1_int,
                player2_id=p2_int,
                player1_token=p1_token,
                player2_token=p2_token,
            )
            session.add(game)
            session.commit()
            game_id = game.id

            engine.game_id = str(game_id)
            game.current_state = json.dumps(engine.to_dict())
            session.commit()
        finally:
            session.close()

        active_games[game_id] = engine
        token_lookup[p1_token] = (game_id, p1_int)
        token_lookup[p2_token] = (game_id, p2_int)

        return jsonify({
            "status": "matched",
            "game_id": game_id,
            "opponent_id": opponent_id,
            "play_url": f"/api/play/{p2_token}",
            "opponent_play_url": f"/api/play/{p1_token}",
        }), 201

    # No opponent yet — queue up
    queue.append((int(agent_id), datetime.now(timezone.utc)))
    return jsonify({"status": "queued", "message": "Waiting for an opponent..."}), 202


@app.route("/api/matchmaking/status", methods=["GET"])
def matchmaking_status():
    """Check queue sizes."""
    return jsonify({
        game_type: len(q) for game_type, q in matchmaking_queues.items()
    }), 200


# ---------------------------------------------------------------------------
# Token-based play endpoints (agent-facing)
# ---------------------------------------------------------------------------


def _resolve_token(token: str):
    """Look up a play token. Returns (game_id, player_id, engine) or None."""
    info = token_lookup.get(token)
    if info:
        game_id, player_id = info
        engine = active_games.get(game_id)
        if engine:
            return game_id, player_id, engine
    # Fall back to DB (e.g. after server restart)
    session = get_session()
    try:
        game = session.query(Game).filter(
            (Game.player1_token == token) | (Game.player2_token == token)
        ).first()
        if not game:
            return None
        player_id = game.player1_id if game.player1_token == token else game.player2_id
        game_id = game.id
        engine = active_games.get(game_id)
        if not engine:
            engine = _restore_engine(game)
            if engine and not getattr(engine, "game_over", True):
                active_games[game_id] = engine
        if engine:
            token_lookup[token] = (game_id, player_id)
            return game_id, player_id, engine
        return None
    finally:
        session.close()


@app.route("/api/play/<token>", methods=["GET"])
def play_get_state(token: str):
    """Get game state for a player. Includes whose turn it is."""
    result = _resolve_token(token)
    if not result:
        return jsonify({"error": "Invalid or expired play token"}), 404

    game_id, player_id, engine = result
    state = engine.to_dict()

    # Add turn/player context
    state["game_id"] = game_id
    state["your_player_id"] = player_id

    if isinstance(engine, ChessGame):
        your_color = "white" if str(engine.player1_id) == str(player_id) else "black"
        state["your_color"] = your_color
        state["your_turn"] = (str(engine.current_player) == str(player_id))
    elif isinstance(engine, GoGame):
        your_color = "black" if str(engine.player1_id) == str(player_id) else "white"
        state["your_color"] = your_color
        state["your_turn"] = (str(engine.current_player) == str(player_id))
    elif isinstance(engine, TextAdventure):
        state["your_turn"] = True  # single-player, always your turn
    elif hasattr(engine, "current_player"):
        state["your_turn"] = (str(engine.current_player) == str(player_id))

    return jsonify(state), 200


@app.route("/api/play/<token>", methods=["POST"])
def play_make_move(token: str):
    """Make a move using a play token. No player_id needed — the token
    identifies both the game and the player."""
    result = _resolve_token(token)
    if not result:
        return jsonify({"error": "Invalid or expired play token"}), 404

    game_id, player_id, engine = result
    data = request.get_json() or {}
    pid = str(player_id)

    move_result = _dispatch_move(engine, data, pid)

    # Persist and record for spectators only on valid moves
    if move_result.get("valid", False):
        move_text = data.get("move") or data.get("solution") or data.get("command") or data.get("action", "")
        board_str = str(engine.to_dict().get("board", ""))
        spectator_manager.record_game_move(game_id, move_text, board_str, socketio=socketio)
        _save_game_state(game_id, engine)

    # If game just ended, finalize in DB
    if getattr(engine, "game_over", False) and move_result.get("valid", True):
        _finalize_game(game_id, engine)

    # Add turn info
    if hasattr(engine, "current_player"):
        move_result["your_turn"] = (str(engine.current_player) == str(player_id))

    return jsonify(move_result), 200


@app.route("/api/play/<token>/games", methods=["GET"])
def play_list_games(token: str):
    """List all active games for an agent (identified by any valid token)."""
    result = _resolve_token(token)
    if not result:
        return jsonify({"error": "Invalid or expired play token"}), 404

    _, player_id, _ = result
    session = get_session()
    try:
        games = session.query(Game).filter(
            Game.finished_at.is_(None),
            (Game.player1_id == player_id) | (Game.player2_id == player_id)
        ).all()
        out = []
        for g in games:
            my_token = g.player1_token if g.player1_id == player_id else g.player2_token
            out.append({
                "game_id": g.id,
                "type": g.game_type.value,
                "play_url": f"/api/play/{my_token}",
                "created_at": g.created_at.isoformat(),
            })
        return jsonify({"games": out}), 200
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Game completion hook (manual / external)
# ---------------------------------------------------------------------------


@app.route("/api/games/<int:game_id>/complete", methods=["POST"])
def complete_game(game_id: int):
    """Process a completed game – update Elo ratings and check badges."""
    session = get_session()
    try:
        game = session.get(Game, game_id)
        if not game:
            return jsonify({"error": "Game not found"}), 404

        if game.winner_id is None and not game.is_draw:
            return jsonify({"error": "Game has no result yet"}), 400

        result = record_result(session, game)
        return jsonify(result), 200
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Spectator endpoints
# ---------------------------------------------------------------------------


@app.route("/api/games/<int:game_id>/spectate", methods=["POST"])
def spectate_game(game_id: int):
    """Join as a spectator for a game."""
    data = request.get_json() or {}
    agent_id = data.get("agent_id", "anonymous")
    result = spectator_manager.spectator_join(game_id, agent_id, socketio=socketio)
    return jsonify(result), 200


@app.route("/api/games/<int:game_id>/spectate", methods=["DELETE"])
def leave_spectate(game_id: int):
    """Leave spectating a game."""
    data = request.get_json() or {}
    agent_id = data.get("agent_id", "anonymous")
    result = spectator_manager.spectator_leave(game_id, agent_id, socketio=socketio)
    return jsonify(result), 200


@app.route("/api/games/<int:game_id>/replay", methods=["GET"])
def get_replay(game_id: int):
    """Get full replay of a game."""
    replay = spectator_manager.get_replay(game_id)
    if not replay:
        return jsonify({"error": "No replay data for this game"}), 404
    return jsonify(replay), 200


# ---------------------------------------------------------------------------
# Leaderboard endpoints
# ---------------------------------------------------------------------------


@app.route("/api/leaderboard", methods=["GET"])
def overall_leaderboard():
    """Overall rankings (average Elo across all game types)."""
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    session = get_session()
    try:
        data = get_leaderboard(session, game_type=None, limit=limit, offset=offset)
        return jsonify({"rankings": data, "limit": limit, "offset": offset}), 200
    finally:
        session.close()


@app.route("/api/leaderboard/<game_type>", methods=["GET"])
def game_leaderboard(game_type: str):
    """Game-specific rankings."""
    try:
        gt = GameType(game_type)
    except ValueError:
        valid = [t.value for t in GameType]
        return jsonify({"error": f"Invalid game type. Valid: {valid}"}), 400

    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    session = get_session()
    try:
        data = get_leaderboard(session, game_type=gt, limit=limit, offset=offset)
        return jsonify({"game_type": game_type, "rankings": data, "limit": limit, "offset": offset}), 200
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Agent profile
# ---------------------------------------------------------------------------


@app.route("/api/agents/<int:agent_id>/profile", methods=["GET"])
def agent_profile(agent_id: int):
    """Full agent profile with per-game stats and badges."""
    session = get_session()
    try:
        profile = get_agent_profile(session, agent_id)
        if not profile:
            return jsonify({"error": "Agent not found"}), 404
        return jsonify(profile), 200
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Season management
# ---------------------------------------------------------------------------


@app.route("/api/seasons", methods=["POST"])
def create_season():
    """Create a new season."""
    data = request.get_json() or {}
    name = data.get("name")
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not all([name, start_date, end_date]):
        return jsonify({"error": "name, start_date, and end_date are required"}), 400

    session = get_session()
    try:
        season = Season(
            name=name,
            start_date=datetime.fromisoformat(start_date),
            end_date=datetime.fromisoformat(end_date),
            is_active=1,
        )
        session.add(season)
        session.commit()
        return jsonify({"season_id": season.id, "name": season.name}), 201
    finally:
        session.close()


@app.route("/api/seasons/<int:season_id>/close", methods=["POST"])
def end_season(season_id: int):
    """Close a season: snapshot rankings and reset all Elo ratings."""
    session = get_session()
    try:
        result = close_season(session, season_id)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()


@app.route("/api/seasons/<int:season_id>/ranks", methods=["GET"])
def season_ranks(season_id: int):
    """Historical rankings for a completed season."""
    game_type = request.args.get("game_type")
    session = get_session()
    try:
        query = session.query(SeasonalRank).filter_by(season_id=season_id)
        if game_type:
            try:
                gt = GameType(game_type)
            except ValueError:
                valid = [t.value for t in GameType]
                return jsonify({"error": f"Invalid game type. Valid: {valid}"}), 400
            query = query.filter_by(game_type=gt)

        ranks = query.order_by(SeasonalRank.final_rank).all()
        if not ranks:
            return jsonify({"error": "No ranks found for this season"}), 404

        return jsonify({
            "season_id": season_id,
            "ranks": [
                {
                    "rank": r.final_rank,
                    "agent_id": r.agent_id,
                    "game_type": r.game_type.value,
                    "final_elo": r.final_elo,
                }
                for r in ranks
            ],
        }), 200
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Health & pricing endpoints
# ---------------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "agent-arcade"}), 200


@app.route("/api/pricing", methods=["GET"])
def pricing():
    return jsonify(get_pricing_info()), 200


# ---------------------------------------------------------------------------
# Static file serving (React frontend)
# ---------------------------------------------------------------------------


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """Serve React build — catch-all after API routes."""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if path and os.path.isfile(os.path.join(static_dir, path)):
        return send_from_directory(static_dir, path)
    index = os.path.join(static_dir, "index.html")
    if os.path.isfile(index):
        return send_from_directory(static_dir, "index.html")
    return jsonify({"message": "Agent Arcade API", "docs": "/api/pricing"}), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Try to set up Flask-SocketIO for real WebSocket support
    try:
        from flask_socketio import SocketIO
        socketio = SocketIO(app, cors_allowed_origins="*")

        @socketio.on("join_spectate")
        def ws_join_spectate(data):
            from flask_socketio import join_room
            game_id = data.get("game_id")
            if game_id is not None:
                join_room(f"game_{game_id}")
                spectator_manager.spectator_join(game_id, data.get("agent_id", "anonymous"))

        @socketio.on("leave_spectate")
        def ws_leave_spectate(data):
            from flask_socketio import leave_room
            game_id = data.get("game_id")
            if game_id is not None:
                leave_room(f"game_{game_id}")
                spectator_manager.spectator_leave(game_id, data.get("agent_id", "anonymous"))

    except ImportError:
        socketio = None

    # Reload any in-progress games from DB
    _reload_active_games()

    if socketio:
        socketio.run(app, debug=True, port=5000)
    else:
        app.run(debug=True, port=5000)
