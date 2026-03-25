"""House Bot — an always-available opponent for Agent Arcade.

When a player joins matchmaking and no opponent is waiting, the house bot
steps in so nobody has to wait. It plays simple but legal moves.
"""

from __future__ import annotations

import random
import threading
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

HOUSE_BOT_NAME = "Arcade Bot"
HOUSE_BOT_DESC = "The house always plays. I'm here so you never wait for an opponent."

# game_id -> bot's play token
_bot_games: dict = {}
_lock = threading.Lock()

_bot_agent_id: Optional[int] = None
_worker_started = False


def get_or_create_bot(session_factory, Agent):
    """Return the house bot's agent ID, creating it on first call."""
    global _bot_agent_id
    if _bot_agent_id is not None:
        return _bot_agent_id

    session = session_factory()
    try:
        # Look for existing house bot
        bot = session.query(Agent).filter_by(name=HOUSE_BOT_NAME).first()
        if bot:
            _bot_agent_id = bot.id
            return _bot_agent_id

        # Create one
        bot = Agent(name=HOUSE_BOT_NAME, description=HOUSE_BOT_DESC)
        session.add(bot)
        session.commit()
        _bot_agent_id = bot.id
        logger.info(f"House bot created with ID {_bot_agent_id}")
        return _bot_agent_id
    finally:
        session.close()


def register_bot_game(game_id: int, token: str):
    """Track a game the house bot is playing in."""
    with _lock:
        _bot_games[game_id] = token


def _unregister_game(game_id: int):
    with _lock:
        _bot_games.pop(game_id, None)


# ---------------------------------------------------------------------------
# Move generation — simple but legal strategies per game type
# ---------------------------------------------------------------------------

def _chess_move(state):
    """Pick a random legal move by trying random piece moves."""
    board = state.get("board", [])
    my_id = str(state.get("your_player_id", ""))
    is_white = state.get("your_color") == "white"

    # Gather our pieces
    pieces = []
    for r in range(8):
        for c in range(8):
            cell = board[r][c] if r < len(board) and c < len(board[r]) else None
            if cell and ((is_white and cell.isupper()) or (not is_white and cell.islower())):
                pieces.append((r, c))

    random.shuffle(pieces)
    files = "abcdefgh"
    ranks = "87654321"

    # Try random destinations for each piece
    targets = [(r, c) for r in range(8) for c in range(8)]
    random.shuffle(targets)

    for pr, pc in pieces:
        for tr, tc in targets:
            if (pr, pc) == (tr, tc):
                continue
            move = f"{files[pc]}{ranks[pr]}-{files[tc]}{ranks[tr]}"
            yield {"move": move}
    # Fallback — shouldn't happen
    yield {"move": "e2-e4"}


def _go_move(state):
    """Place a stone on a random empty intersection, or pass."""
    board = state.get("board", [])
    size = len(board)
    cols = "ABCDEFGHJ"  # Go skips I

    empties = []
    for r in range(size):
        for c in range(size):
            if board[r][c] == 0:
                empties.append((r, c))

    random.shuffle(empties)
    for r, c in empties:
        col_letter = cols[c] if c < len(cols) else chr(ord("A") + c)
        row_num = size - r
        yield {"move": f"{col_letter}{row_num}"}

    yield {"move": "pass"}


def _poker_move(state):
    """Simple poker strategy: check when free, call most of the time, occasionally raise."""
    phase = state.get("phase", "")
    bets = state.get("bets", {})
    my_id = str(state.get("your_player_id", ""))
    chips = state.get("chips", {})
    my_chips = chips.get(my_id, 1000)

    # Find if we need to call
    other_bet = 0
    my_bet = bets.get(my_id, 0)
    for pid, b in bets.items():
        if str(pid) != my_id:
            other_bet = max(other_bet, b)

    needs_call = other_bet > my_bet

    roll = random.random()
    if not needs_call:
        # Can check for free
        if roll < 0.7:
            yield {"action": "check"}
        else:
            amount = min(max(20, int(my_chips * 0.1)), my_chips)
            yield {"action": "raise", "amount": amount}
            yield {"action": "check"}
    else:
        if roll < 0.15:
            yield {"action": "fold"}
        elif roll < 0.8:
            yield {"action": "call"}
        else:
            amount = min(max(other_bet * 2, 40), my_chips)
            yield {"action": "raise", "amount": amount}
            yield {"action": "call"}


def _negotiation_move(state):
    """Propose even splits or accept reasonable proposals."""
    pool = state.get("pool", {})
    proposal = state.get("current_proposal")
    my_id = str(state.get("your_player_id", ""))

    # If there's a proposal pending and it's our turn, accept ~60% of the time
    if proposal:
        if random.random() < 0.6:
            yield {"action": "accept"}
        else:
            yield {"action": "reject"}
        yield {"action": "accept"}
    else:
        # Make a proposal — give ourselves 55-65% of each resource
        my_share = {}
        for resource, amount in pool.items():
            take = max(1, int(amount * random.uniform(0.5, 0.65)))
            my_share[resource] = min(take, amount)
        yield {"action": "propose", "proposal": {my_id: my_share}}
        # Fallback: even split
        even = {r: amount // 2 for r, amount in pool.items()}
        yield {"action": "propose", "proposal": {my_id: even}}


def _reasoning_move(state):
    """Try common numeric answers for reasoning puzzles."""
    puzzle = state.get("current_puzzle", {})
    prompt = puzzle.get("prompt", "") if isinstance(puzzle, dict) else str(puzzle)

    # Try to extract numbers from the prompt as candidate answers
    import re
    numbers = re.findall(r"\d+", prompt)
    # Try some computed guesses
    guesses = list(set(numbers + ["42", "0", "1", "2", "100", "10"]))
    random.shuffle(guesses)
    for g in guesses:
        yield {"answer": g}
    yield {"answer": "42"}


def _code_challenge_move(state):
    """Submit a basic solution attempt."""
    challenge = state.get("challenge", {})
    key = state.get("challenge_key", "")

    # Generic solutions for common challenges
    solutions = [
        "def solve(n):\n    return n",
        "def solve(n):\n    return n * 2",
        "def solve(n):\n    return sum(range(n + 1))",
        "def solve(n):\n    return n ** 2",
        "def solve(s):\n    return s[::-1]",
        "def solve(n):\n    return [i for i in range(2, n + 1) if all(i % j for j in range(2, int(i**0.5)+1))]",
    ]
    random.shuffle(solutions)
    for s in solutions:
        yield {"solution": s}


def _get_move_candidates(state):
    """Return a generator of move dicts to try, based on game type."""
    game_type = state.get("type", "chess")
    generators = {
        "chess": _chess_move,
        "go": _go_move,
        "poker": _poker_move,
        "negotiation": _negotiation_move,
        "reasoning": _reasoning_move,
        "code_challenge": _code_challenge_move,
    }
    gen = generators.get(game_type, _chess_move)
    return gen(state)


# ---------------------------------------------------------------------------
# Background worker — uses engine internals directly (no HTTP)
# ---------------------------------------------------------------------------

# These get set by start_worker() so the thread can access app internals
_app_refs = {}


def _bot_worker():
    """Background thread that plays moves for the house bot."""
    time.sleep(2)  # let server finish init

    while True:
        try:
            with _lock:
                games = dict(_bot_games)

            if not games:
                time.sleep(2)
                continue

            active_games = _app_refs.get("active_games", {})
            token_lookup = _app_refs.get("token_lookup", {})
            dispatch_move = _app_refs.get("dispatch_move")
            save_state = _app_refs.get("save_state")
            finalize = _app_refs.get("finalize")

            for game_id, token in games.items():
                try:
                    lookup = token_lookup.get(token)
                    if not lookup:
                        _unregister_game(game_id)
                        continue

                    gid, player_id = lookup
                    engine = active_games.get(gid)
                    if not engine:
                        _unregister_game(game_id)
                        continue

                    if getattr(engine, "game_over", False):
                        _unregister_game(game_id)
                        continue

                    # Check if it's our turn
                    current = str(getattr(engine, "current_player", ""))
                    if current != str(player_id):
                        continue

                    # Build state dict for move generation
                    state = engine.to_dict()
                    state["your_player_id"] = player_id

                    # Determine color for chess/go
                    p1 = str(getattr(engine, "player1_id", ""))
                    if state.get("type") == "chess":
                        state["your_color"] = "white" if p1 == str(player_id) else "black"
                    elif state.get("type") == "go":
                        state["your_color"] = "black" if p1 == str(player_id) else "white"
                    state["your_turn"] = True

                    # Try moves until one works
                    played = False
                    for move_data in _get_move_candidates(state):
                        if dispatch_move:
                            result = dispatch_move(engine, move_data, str(player_id))
                        else:
                            break
                        if result and result.get("valid"):
                            logger.info(f"House bot played in game {gid}: {move_data}")
                            if save_state:
                                save_state(gid, engine)
                            if getattr(engine, "game_over", False) and finalize:
                                finalize(gid, engine)
                            played = True
                            break

                    if not played:
                        logger.warning(f"House bot couldn't find valid move for game {gid}")

                except Exception as e:
                    logger.error(f"House bot error in game {game_id}: {e}")

        except Exception as e:
            logger.error(f"House bot worker error: {e}")

        # Delay 1.5-3s to feel natural
        time.sleep(random.uniform(1.5, 3.0))


def start_worker(app):
    """Start the background worker thread (idempotent).

    Must be called after app.py defines active_games, token_lookup, etc.
    We defer grabbing those references until the first tick of the worker
    to avoid import-order issues. Instead, app.py calls set_app_refs().
    """
    global _worker_started
    if _worker_started:
        return
    _worker_started = True
    t = threading.Thread(target=_bot_worker, daemon=True)
    t.start()
    logger.info("House bot worker started")


def set_app_refs(active_games, token_lookup, dispatch_move, save_state, finalize):
    """Give the worker access to app internals without circular imports."""
    _app_refs["active_games"] = active_games
    _app_refs["token_lookup"] = token_lookup
    _app_refs["dispatch_move"] = dispatch_move
    _app_refs["save_state"] = save_state
    _app_refs["finalize"] = finalize
