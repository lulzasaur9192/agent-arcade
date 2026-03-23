"""Automated tournament: multiple agents play chess games continuously.

Run with: python3 tournament.py
Requires the Flask server running on :5000
"""
import json
import random
import time
import sys
import requests

BASE = "http://localhost:5000"

AGENTS = ["AlphaBot", "BetaBot", "GammaBot", "DeltaBot", "EpsilonBot", "ZetaBot"]

# Common chess openings and responses for variety
OPENINGS = [
    ["e2-e4", "e7-e5", "g1-f3", "b8-c6", "f1-b5"],  # Ruy Lopez
    ["d2-d4", "d7-d5", "c2-c4", "e7-e6", "b1-c3"],  # Queen's Gambit
    ["e2-e4", "c7-c5", "g1-f3", "d7-d6", "d2-d4"],  # Sicilian
    ["e2-e4", "e7-e5", "f1-c4", "g8-f6", "d2-d3"],  # Italian
    ["d2-d4", "g8-f6", "c2-c4", "g7-g6", "b1-c3"],  # King's Indian
]

# Random middle-game moves by piece type
PIECE_MOVES = {
    'P': lambda r, c, w: [(r + (-1 if w else 1), c), (r + (-2 if w else 2), c),
                           (r + (-1 if w else 1), c - 1), (r + (-1 if w else 1), c + 1)],
    'N': lambda r, c, _: [(r-2,c-1),(r-2,c+1),(r-1,c-2),(r-1,c+2),
                           (r+1,c-2),(r+1,c+2),(r+2,c-1),(r+2,c+1)],
    'B': lambda r, c, _: [(r+d*i, c+e*i) for d in [-1,1] for e in [-1,1] for i in range(1,8)],
    'R': lambda r, c, _: [(r+i,c) for i in range(-7,8) if i!=0] + [(r,c+i) for i in range(-7,8) if i!=0],
    'Q': lambda r, c, _: [(r+d*i,c+e*i) for d in [-1,0,1] for e in [-1,0,1] if (d,e)!=(0,0) for i in range(1,8)],
    'K': lambda r, c, _: [(r+d,c+e) for d in [-1,0,1] for e in [-1,0,1] if (d,e)!=(0,0)],
}

COLS = "abcdefgh"


def api(method, path, data=None):
    url = f"{BASE}{path}" if path.startswith("/api") else f"{BASE}/api{path}"
    r = getattr(requests, method)(url, json=data, timeout=10)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:200]}


def to_algebraic(r, c):
    return f"{COLS[c]}{8 - r}"


def from_algebraic(s):
    return 8 - int(s[1]), COLS.index(s[0])


def find_random_move(board, is_white_turn):
    """Find a random legal-looking move for the current side."""
    moves = []
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece is None:
                continue
            pw = piece.isupper()
            if pw != is_white_turn:
                continue

            p = piece.upper()
            if p not in PIECE_MOVES:
                continue

            targets = PIECE_MOVES[p](r, c, pw)
            for tr, tc in targets:
                if 0 <= tr < 8 and 0 <= tc < 8:
                    target = board[tr][tc]
                    # Can't capture own pieces
                    if target and target.isupper() == pw:
                        continue
                    moves.append(f"{to_algebraic(r, c)}-{to_algebraic(tr, tc)}")

    random.shuffle(moves)
    return moves


def play_game(game_id, p1_token, p2_token, p1_name, p2_name):
    """Play a full game between two agents using random moves."""
    tokens = [p1_token, p2_token]
    names = [p1_name, p2_name]
    turn = 0
    max_moves = 100  # Safety cap

    # Try an opening first
    opening = random.choice(OPENINGS)

    for move_num in range(max_moves):
        token = tokens[turn % 2]
        name = names[turn % 2]

        # Use opening moves if available
        if move_num < len(opening):
            move = opening[move_num]
            code, body = api("post", token, {"move": move})
            if body.get("valid"):
                print(f"  Move {move_num + 1}: {name} plays {move} (opening)")
                if body.get("game_over"):
                    winner = body.get("winner", "?")
                    reason = body.get("reason", "?")
                    print(f"  >> GAME OVER: winner={winner}, reason={reason}")
                    return body
                turn += 1
                continue

        # Get current game state to find valid moves
        code, state = api("get", f"/api/games/{game_id}")
        if code != 200:
            print(f"  Game {game_id} no longer active")
            return None

        board = state.get("board", [])
        is_white = (turn % 2 == 0)
        candidates = find_random_move(board, is_white)

        moved = False
        for move in candidates:
            code, body = api("post", token, {"move": move})
            if body.get("valid"):
                if move_num % 5 == 0 or body.get("game_over"):  # Print every 5th move
                    print(f"  Move {move_num + 1}: {name} plays {move}")
                if body.get("game_over"):
                    winner = body.get("winner", "?")
                    reason = body.get("reason", "?")
                    print(f"  >> GAME OVER: winner={winner}, reason={reason}")
                    return body
                turn += 1
                moved = True
                break

        if not moved:
            print(f"  {name} has no valid moves — game likely over")
            return None

    print(f"  Game #{game_id} reached {max_moves} moves — ending")
    return None


def main():
    print("=" * 60)
    print("AGENT ARCADE — AUTOMATED TOURNAMENT")
    print("=" * 60)

    # Register agents
    print("\n[1/3] Registering agents...")
    agent_ids = {}
    for name in AGENTS:
        code, body = api("post", "/agents/register", {"name": name})
        if code == 201:
            agent_ids[name] = body["id"]
            print(f"  Registered {name} (id={body['id']})")
        elif code == 409:
            agent_ids[name] = body["id"]
            print(f"  {name} exists (id={body['id']})")
        else:
            print(f"  Failed: {body}")
            return

    # Run tournament rounds
    num_rounds = 3
    print(f"\n[2/3] Running {num_rounds} rounds of chess...")

    for round_num in range(1, num_rounds + 1):
        print(f"\n{'─' * 40}")
        print(f"ROUND {round_num}")
        print(f"{'─' * 40}")

        # Shuffle and pair up agents
        names = list(agent_ids.keys())
        random.shuffle(names)
        pairs = [(names[i], names[i + 1]) for i in range(0, len(names) - 1, 2)]

        for p1_name, p2_name in pairs:
            print(f"\n  {p1_name} vs {p2_name}")
            code, body = api("post", "/games/create", {
                "type": "chess",
                "player1_id": agent_ids[p1_name],
                "player2_id": agent_ids[p2_name],
            })
            if code != 201:
                print(f"  Failed to create game: {body}")
                continue

            game_id = body["id"]
            p1_token = body["play_urls"]["player1"]
            p2_token = body["play_urls"]["player2"]
            print(f"  Game #{game_id} started")

            play_game(game_id, p1_token, p2_token, p1_name, p2_name)

    # Print final standings
    print(f"\n{'=' * 60}")
    print("FINAL STANDINGS")
    print(f"{'=' * 60}")

    code, body = api("get", "/leaderboard/chess")
    rankings = body.get("rankings", [])
    if rankings:
        print(f"\n{'Rank':<6}{'Agent':<15}{'ELO':<10}{'W':<5}{'L':<5}{'D':<5}{'Streak':<8}")
        print("─" * 54)
        for e in rankings:
            print(f"#{e['rank']:<5}{e.get('agent_name','?'):<15}{e['elo']:<10.1f}{e['wins']:<5}{e['losses']:<5}{e['draws']:<5}{e.get('streak',0):<8}")
    else:
        print("  No rankings yet")

    # Overall
    code, body = api("get", "/leaderboard")
    overall = body.get("rankings", [])
    if overall:
        print(f"\nOverall leaderboard: {len(overall)} agents ranked")

    # Active games
    code, body = api("get", "/games")
    games = body.get("games", [])
    active = [g for g in games if not g.get("game_over")]
    print(f"Active games: {len(active)}")
    print(f"Total games played: {len(games)}")

    print(f"\n{'=' * 60}")
    print("TOURNAMENT COMPLETE")
    print(f"{'=' * 60}")
    print(f"\nView live at: http://localhost:3000 (frontend)")
    print(f"API at: http://localhost:5000/api/leaderboard")


if __name__ == "__main__":
    try:
        main()
    except requests.ConnectionError:
        print("ERROR: Cannot connect to server at :5000. Start with: python3 app.py")
        sys.exit(1)
