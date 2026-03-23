"""End-to-end test: register agents, create games, play moves, verify results."""
import json
import sys
import time
import requests

BASE = "http://localhost:5000"

def api(method, path, data=None):
    # If path doesn't start with /api, add it
    if not path.startswith("/api"):
        path = f"/api{path}"
    url = f"{BASE}{path}"
    r = getattr(requests, method)(url, json=data, timeout=10)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:500]}
    if r.status_code >= 400:
        print(f"  ERROR {r.status_code}: {body}")
    return r.status_code, body


def main():
    print("=" * 60)
    print("AGENT ARCADE — END-TO-END TEST")
    print("=" * 60)

    # 1. Register agents
    print("\n--- Registering agents ---")
    agents = {}
    for name in ["AlphaBot", "BetaBot", "GammaBot", "DeltaBot"]:
        code, body = api("post", "/agents/register", {"name": name})
        if code == 201:
            agents[name] = body["id"]
            print(f"  Registered {name} (id={body['id']})")
        elif code == 409:
            agents[name] = body["id"]
            print(f"  {name} already exists (id={body['id']})")
        else:
            print(f"  Failed to register {name}: {body}")
            return False

    # Verify agent list
    code, body = api("get", "/agents")
    print(f"  Total agents: {len(body.get('agents', []))}")

    # 2. Create chess games
    print("\n--- Creating chess games ---")
    games = []

    for p1, p2 in [("AlphaBot", "BetaBot"), ("GammaBot", "DeltaBot")]:
        code, body = api("post", "/games/create", {
            "type": "chess",
            "player1_id": agents[p1],
            "player2_id": agents[p2],
        })
        if code == 201:
            games.append({
                "id": body["id"],
                "p1": p1, "p2": p2,
                "p1_url": body["play_urls"]["player1"],
                "p2_url": body["play_urls"]["player2"],
            })
            print(f"  Game #{body['id']}: {p1} vs {p2}")
        else:
            print(f"  Failed: {body}")
            return False

    # 3. Play some chess moves via token-based API
    print("\n--- Playing chess moves ---")
    g = games[0]

    # Scholar's mate attempt (4-move checkmate)
    moves = [
        (g["p1_url"], "e2-e4"),  # White
        (g["p2_url"], "e7-e5"),  # Black
        (g["p1_url"], "f1-c4"),  # White bishop
        (g["p2_url"], "b8-c6"),  # Black knight
        (g["p1_url"], "d1-h5"),  # White queen
        (g["p2_url"], "g8-f6"),  # Black knight (blocks)
        (g["p1_url"], "h5-f7"),  # White queen takes f7 = checkmate
    ]

    for token_path, move in moves:
        code, body = api("post", token_path, {"move": move})
        valid = body.get("valid", False)
        game_over = body.get("game_over", False)
        print(f"  {move}: valid={valid}, game_over={game_over}")
        if not valid:
            print(f"    Reason: {body.get('error', body.get('reason', 'unknown'))}")
        if game_over:
            winner = body.get("winner", "?")
            reason = body.get("reason", "?")
            print(f"    GAME OVER — winner={winner}, reason={reason}")
            break

    # 4. Play game 2 with a few moves (don't finish)
    print("\n--- Game 2: partial play ---")
    g2 = games[1]
    for token_path, move in [(g2["p1_url"], "d2-d4"), (g2["p2_url"], "d7-d5"), (g2["p1_url"], "c2-c4")]:
        code, body = api("post", token_path, {"move": move})
        print(f"  {move}: valid={body.get('valid')}")

    # 5. Check active games
    print("\n--- Active games ---")
    code, body = api("get", "/games")
    for g in body.get("games", []):
        print(f"  Game #{g['id']}: type={g['type']}, game_over={g['game_over']}")

    # 6. Test matchmaking
    print("\n--- Matchmaking test ---")
    code, body = api("post", "/matchmaking/join", {"agent_id": agents["AlphaBot"], "type": "chess"})
    print(f"  AlphaBot joins queue: status={body.get('status')}")

    code, body = api("post", "/matchmaking/join", {"agent_id": agents["BetaBot"], "type": "chess"})
    print(f"  BetaBot joins queue: status={body.get('status')}")
    if body.get("status") == "matched":
        print(f"  Matched! game_id={body.get('game_id')}")

    # 7. Check leaderboard
    print("\n--- Leaderboard ---")
    code, body = api("get", "/leaderboard")
    for entry in body.get("rankings", []):
        print(f"  #{entry['rank']} {entry.get('agent_name', '?')} — elo={entry.get('elo', entry.get('avg_elo', '?'))}, W={entry.get('wins', entry.get('total_wins', 0))}, L={entry.get('losses', entry.get('total_losses', 0))}")

    # 8. Check chess-specific leaderboard
    code, body = api("get", "/leaderboard/chess")
    print(f"\n  Chess leaderboard: {len(body.get('rankings', []))} entries")
    for entry in body.get("rankings", []):
        print(f"    #{entry['rank']} {entry.get('agent_name', '?')} — elo={entry.get('elo', '?')}")

    # 9. Check agent profile
    print("\n--- Agent profile: AlphaBot ---")
    code, body = api("get", f"/agents/{agents['AlphaBot']}/profile")
    if code == 200:
        print(f"  Name: {body.get('agent_name')}")
        print(f"  Total games: {body.get('total_games')}")
        print(f"  Wins: {body.get('overall_wins')}, Losses: {body.get('overall_losses')}")
        for game_type, stats in body.get("game_stats", {}).items():
            print(f"  {game_type}: elo={stats['elo']}, W={stats['wins']}, L={stats['losses']}")
        badges = body.get("badges", [])
        if badges:
            print(f"  Badges: {[b['badge'] for b in badges]}")

    # 10. Test code challenge
    print("\n--- Code Challenge game ---")
    code, body = api("post", "/games/create", {
        "type": "code_challenge",
        "player1_id": agents["AlphaBot"],
        "player2_id": agents["BetaBot"],
    })
    if code == 201:
        cc_id = body["id"]
        cc_p1 = body["play_urls"]["player1"]
        cc_p2 = body["play_urls"]["player2"]
        print(f"  Created code challenge #{cc_id}")

        # Submit solutions
        code, body = api("post", cc_p1, {"solution": "def solve(n): return n * (n + 1) // 2"})
        print(f"  AlphaBot submitted: valid={body.get('valid')}, score={body.get('score')}")

        code, body = api("post", cc_p2, {"solution": "def solve(n): return sum(range(1, n+1))"})
        print(f"  BetaBot submitted: valid={body.get('valid')}, score={body.get('score')}")

    # 11. Test text adventure
    print("\n--- Text Adventure game ---")
    code, body = api("post", "/games/create", {
        "type": "text_adventure",
        "player1_id": agents["GammaBot"],
    })
    if code == 201:
        ta_p1 = body["play_urls"]["player1"]
        print(f"  Created text adventure #{body['id']}")

        for cmd in ["look", "go north", "look"]:
            code, body = api("post", ta_p1, {"command": cmd})
            print(f"  '{cmd}': {body.get('message', body.get('description', ''))[:80]}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except requests.ConnectionError:
        print("ERROR: Cannot connect to server. Start it with: python3 app.py")
        sys.exit(1)
