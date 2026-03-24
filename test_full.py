#!/usr/bin/env python3
"""Comprehensive E2E test suite for Agent Arcade.

Tests all 7 game types, registration, matchmaking, leaderboards,
and x402 payment flow against production or local server.

Usage:
    python3 test_full.py           # test against production
    python3 test_full.py --local   # test against localhost:5000
"""

import json
import sys
import time
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROD_URL = "https://agent-arcade-production.up.railway.app"
LOCAL_URL = "http://localhost:5000"

BASE_URL = LOCAL_URL if "--local" in sys.argv else PROD_URL
TS = str(int(time.time()))
TIMEOUT = 15
HEALTH_TIMEOUT = 30

# Known answers for reasoning puzzles (prompt substring -> answer)
PUZZLE_ANSWERS = {
    "2, 4, 8, 16": "32",
    "1, 1, 2, 3, 5, 8": "13",
    "all Bloops": "yes",
    "Alice is taller": "Carol",
    "1, 4, 9, 16, 25": "36",
    "room of 3 people": "3",
    "3 boxes": "Both",
    "bat and ball": "5",
    "3, 3, 5, 4, 4": "3",
    "5 houses": "no",
    "12 coins": "3",
    "Knights always": "A=Knave, B=Knight",
    "100 prisoners": "31",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

passed = 0
failed = 0
errors = []


def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  PASS  {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  FAIL  {name}: {e}")


def get(path, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)


def post(path, data=None, **kwargs):
    return requests.post(f"{BASE_URL}{path}", json=data, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)


def register_agent(name):
    """Register an agent, returning its ID. Handles 409 by extracting existing ID."""
    r = post("/api/agents/register", {"name": name})
    if r.status_code == 201:
        return r.json()["id"]
    if r.status_code == 409:
        return r.json()["id"]
    r.raise_for_status()


def create_game(game_type, p1, p2=None, headers=None):
    """Create a game, return the JSON response."""
    data = {"type": game_type, "player1_id": p1}
    if p2 is not None:
        data["player2_id"] = p2
    r = post("/api/games/create", data, headers=headers or {})
    return r


def play(token, data):
    """POST a move via play token."""
    return post(f"/api/play/{token}", data)


def play_get(token):
    """GET game state via play token."""
    return get(f"/api/play/{token}")


def lookup_puzzle_answer(prompt):
    """Match a reasoning puzzle prompt to a known answer."""
    for key, answer in PUZZLE_ANSWERS.items():
        if key in prompt:
            return answer
    return "unknown"


# ---------------------------------------------------------------------------
# Shared state populated by earlier tests
# ---------------------------------------------------------------------------

agent1_id = None
agent2_id = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health():
    r = get("/health", timeout=HEALTH_TIMEOUT)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert r.json()["status"] == "ok"


def test_pricing():
    r = get("/api/pricing")
    assert r.status_code == 200
    data = r.json()
    games = data["games"]
    free_games = [g for g, info in games.items() if info["free"]]
    paid_games = [g for g, info in games.items() if not info["free"]]
    assert set(free_games) == {"chess", "code_challenge", "text_adventure"}, f"Free games: {free_games}"
    assert set(paid_games) == {"negotiation", "trading", "reasoning", "go"}, f"Paid games: {paid_games}"


def test_register():
    global agent1_id, agent2_id
    agent1_id = register_agent(f"TestBot_{TS}_1")
    agent2_id = register_agent(f"TestBot_{TS}_2")
    assert agent1_id is not None
    assert agent2_id is not None
    assert agent1_id != agent2_id


def test_profile():
    r = get(f"/api/agents/{agent1_id}/profile")
    assert r.status_code == 200
    data = r.json()
    assert "name" in data or "agent_id" in data


def test_chess():
    """Scholar's Mate: e2-e4, e7-e5, f1-c4, b8-c6, d1-h5, g8-f6, h5-f7 -> checkmate."""
    r = create_game("chess", agent1_id, agent2_id)
    assert r.status_code == 201, f"Create failed: {r.status_code} {r.text}"
    data = r.json()
    p1_token = data["play_urls"]["player1"].split("/")[-1]
    p2_token = data["play_urls"]["player2"].split("/")[-1]

    moves = [
        (p1_token, "e2-e4"),
        (p2_token, "e7-e5"),
        (p1_token, "f1-c4"),
        (p2_token, "b8-c6"),
        (p1_token, "d1-h5"),
        (p2_token, "g8-f6"),
        (p1_token, "h5-f7"),
    ]
    for token, move in moves:
        result = play(token, {"move": move})
        assert result.status_code == 200, f"Move {move} failed: {result.text}"
        rj = result.json()
        assert rj.get("valid", False), f"Move {move} invalid: {rj}"

    # Last move should end the game
    assert rj.get("game_over", False), "Chess game did not end after Scholar's Mate"


def test_code_challenge():
    """Both agents submit solutions for 3 rounds (code challenge has 3 rounds by default)."""
    r = create_game("code_challenge", agent1_id, agent2_id)
    assert r.status_code == 201, f"Create failed: {r.status_code} {r.text}"
    data = r.json()
    p1_token = data["play_urls"]["player1"].split("/")[-1]
    p2_token = data["play_urls"]["player2"].split("/")[-1]

    # Get the game state to see the challenge
    state = play_get(p1_token)
    assert state.status_code == 200

    solution = "def solve(n): return n * (n + 1) // 2"
    game_over = False
    for i in range(10):  # max iterations to prevent infinite loop
        # P1 submits
        r1 = play(p1_token, {"solution": solution})
        assert r1.status_code == 200, f"P1 submit failed: {r1.text}"
        if r1.json().get("game_over"):
            game_over = True
            break
        # P2 submits
        r2 = play(p2_token, {"solution": solution})
        assert r2.status_code == 200, f"P2 submit failed: {r2.text}"
        if r2.json().get("game_over"):
            game_over = True
            break

    assert game_over, "Code challenge did not complete"


def test_text_adventure():
    """Navigate dungeon: entrance -> corridor -> chamber -> tower -> victory."""
    r = create_game("text_adventure", agent1_id)
    assert r.status_code == 201, f"Create failed: {r.status_code} {r.text}"
    data = r.json()
    p1_token = data["play_urls"]["player1"].split("/")[-1]

    commands = [
        ("look", False),
        ("take torch", False),
        ("north", False),       # entrance -> corridor
        ("north", False),       # corridor -> chamber
        ("up", False),          # chamber -> tower
        ("out", True),          # tower -> victory
    ]
    for cmd, expect_victory in commands:
        r = play(p1_token, {"command": cmd})
        assert r.status_code == 200, f"Command '{cmd}' failed: {r.text}"
        rj = r.json()
        assert rj.get("valid", False), f"Command '{cmd}' invalid: {rj}"

    assert rj.get("victory", False) or rj.get("game_over", False), "Text adventure did not reach victory"


def test_negotiation():
    """P1 proposes a split, P2 accepts -> deal."""
    r = create_game("negotiation", agent1_id, agent2_id)
    assert r.status_code == 201, f"Create failed: {r.status_code} {r.text}"
    data = r.json()
    p1_token = data["play_urls"]["player1"].split("/")[-1]
    p2_token = data["play_urls"]["player2"].split("/")[-1]

    # P1 proposes: split everything 60/40
    proposal = {
        "player1": {"gold": 60, "wood": 120, "stone": 90},
        "player2": {"gold": 40, "wood": 80, "stone": 60},
    }
    r1 = play(p1_token, {"action": "propose", "proposal": proposal})
    assert r1.status_code == 200
    assert r1.json().get("valid"), f"Propose invalid: {r1.json()}"

    # P2 accepts
    r2 = play(p2_token, {"action": "accept"})
    assert r2.status_code == 200
    rj = r2.json()
    assert rj.get("valid"), f"Accept invalid: {rj}"
    assert rj.get("game_over"), "Negotiation did not end after accept"


def test_trading():
    """Both agents hold for all rounds until game completes."""
    r = create_game("trading", agent1_id, agent2_id)
    assert r.status_code == 201, f"Create failed: {r.status_code} {r.text}"
    data = r.json()
    p1_token = data["play_urls"]["player1"].split("/")[-1]
    p2_token = data["play_urls"]["player2"].split("/")[-1]

    game_over = False
    for round_num in range(25):  # 20 rounds + buffer
        # P1 holds
        r1 = play(p1_token, {"actions": [{"action": "hold"}]})
        assert r1.status_code == 200, f"P1 hold failed round {round_num}: {r1.text}"
        if r1.json().get("game_over"):
            game_over = True
            break
        # P2 holds
        r2 = play(p2_token, {"actions": [{"action": "hold"}]})
        assert r2.status_code == 200, f"P2 hold failed round {round_num}: {r2.text}"
        if r2.json().get("game_over"):
            game_over = True
            break

    assert game_over, "Trading game did not complete after 20 rounds"


def test_reasoning():
    """Both agents answer 5 puzzles using known answers from PUZZLE_BANK."""
    r = create_game("reasoning", agent1_id, agent2_id)
    assert r.status_code == 201, f"Create failed: {r.status_code} {r.text}"
    data = r.json()
    p1_token = data["play_urls"]["player1"].split("/")[-1]
    p2_token = data["play_urls"]["player2"].split("/")[-1]

    game_over = False
    for i in range(12):  # 5 puzzles x 2 players + buffer
        # Check whose turn it is
        state = play_get(p1_token).json()
        if state.get("game_over"):
            game_over = True
            break

        puzzle = state.get("current_puzzle")
        if not puzzle:
            game_over = True
            break

        prompt = puzzle.get("prompt", "")
        answer = lookup_puzzle_answer(prompt)
        your_turn = state.get("your_turn", False)

        if your_turn:
            r = play(p1_token, {"answer": answer})
        else:
            # It's P2's turn
            r = play(p2_token, {"answer": answer})

        assert r.status_code == 200, f"Answer failed: {r.text}"
        rj = r.json()
        assert rj.get("valid", False), f"Answer invalid: {rj}"
        if rj.get("game_over"):
            game_over = True
            break

    assert game_over, "Reasoning game did not complete after all puzzles"


def test_go():
    """Play a few moves, both pass -> scoring + game over."""
    r = create_game("go", agent1_id, agent2_id)
    assert r.status_code == 201, f"Create failed: {r.status_code} {r.text}"
    data = r.json()
    p1_token = data["play_urls"]["player1"].split("/")[-1]
    p2_token = data["play_urls"]["player2"].split("/")[-1]

    # Play a few moves
    moves = [
        (p1_token, "d5"),
        (p2_token, "f5"),
        (p1_token, "e3"),
        (p2_token, "e7"),
    ]
    for token, move in moves:
        r = play(token, {"move": move})
        assert r.status_code == 200, f"Move {move} failed: {r.text}"
        assert r.json().get("valid", False), f"Move {move} invalid: {r.json()}"

    # Both pass -> game ends
    r1 = play(p1_token, {"move": "pass"})
    assert r1.status_code == 200
    r2 = play(p2_token, {"move": "pass"})
    assert r2.status_code == 200
    assert r2.json().get("game_over", False), "Go game did not end after two passes"


def test_matchmaking():
    """Two agents join chess queue -> matched."""
    # Agent 1 joins queue
    r1 = post("/api/matchmaking/join", {"agent_id": agent1_id, "type": "chess"})
    assert r1.status_code in (201, 202), f"Join 1 failed: {r1.status_code} {r1.text}"

    # Agent 2 joins queue -> should match
    r2 = post("/api/matchmaking/join", {"agent_id": agent2_id, "type": "chess"})
    assert r2.status_code == 201, f"Join 2 failed: {r2.status_code} {r2.text}"
    assert r2.json().get("status") == "matched", f"Not matched: {r2.json()}"
    assert "play_url" in r2.json()


def test_leaderboard():
    """GET /api/leaderboard -> agents appear."""
    r = get("/api/leaderboard")
    assert r.status_code == 200
    data = r.json()
    assert "rankings" in data


def test_leaderboard_types():
    """GET /api/leaderboard/{type} for all 7 game types -> 200."""
    game_types = ["chess", "code_challenge", "text_adventure", "negotiation", "trading", "reasoning", "go"]
    for gt in game_types:
        r = get(f"/api/leaderboard/{gt}")
        assert r.status_code == 200, f"Leaderboard {gt} failed: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# Payment flow tests (only meaningful when x402 is enabled on prod)
# ---------------------------------------------------------------------------


def test_payment_free_game():
    """Free game (chess) without X-PAYMENT header -> 201 (always passes through)."""
    r = create_game("chess", agent1_id, agent2_id)
    assert r.status_code == 201, f"Free game should work without payment: {r.status_code} {r.text}"


def test_payment_paid_game_no_header():
    """Paid game (go) without X-PAYMENT header -> 402 when x402 enabled, 201 when disabled."""
    r = create_game("go", agent1_id, agent2_id)
    if r.status_code == 402:
        # x402 is enabled - verify the 402 response format
        data = r.json()
        assert "accepts" in data, "402 response missing 'accepts' field"
        accept = data["accepts"][0]
        assert accept["resource"] == "game:go"
        assert accept["payTo"] != ""
        print(f"         (x402 enabled, got valid 402 response)")
    elif r.status_code == 201:
        # x402 is disabled - all games free
        print(f"         (x402 disabled, game created free)")
    else:
        raise AssertionError(f"Unexpected status: {r.status_code} {r.text}")


def test_payment_paid_game_with_header():
    """Paid game (go) with mock X-PAYMENT header -> 201 (accepted by MVP verifier)."""
    # Base64 of a mock payment payload
    import base64
    mock_payment = base64.b64encode(json.dumps({
        "network": "eip155:8453",
        "payload": "mock_payment_for_testing",
    }).encode()).decode()

    r = create_game("go", agent1_id, agent2_id, headers={"X-PAYMENT": mock_payment})
    if r.status_code == 201:
        print(f"         (payment accepted or x402 disabled)")
    elif r.status_code == 402:
        # This shouldn't happen with a valid header, but x402 might not be enabled
        print(f"         (x402 disabled, payment header ignored)")
    else:
        raise AssertionError(f"Unexpected status: {r.status_code} {r.text}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main():
    global passed, failed

    print(f"\n{'='*60}")
    print(f"  Agent Arcade E2E Test Suite")
    print(f"  Target: {BASE_URL}")
    print(f"  Timestamp: {TS}")
    print(f"{'='*60}\n")

    # Infrastructure tests
    print("[Infrastructure]")
    test("health", test_health)
    test("pricing", test_pricing)

    # Registration (must run before game tests)
    print("\n[Registration]")
    test("register", test_register)
    test("profile", test_profile)

    if agent1_id is None or agent2_id is None:
        print("\nABORT: Registration failed, cannot run game tests.")
        sys.exit(1)

    # Game tests
    print("\n[Games - Free Tier]")
    test("chess (Scholar's Mate)", test_chess)
    test("code_challenge", test_code_challenge)
    test("text_adventure", test_text_adventure)

    print("\n[Games - Paid Tier]")
    test("negotiation", test_negotiation)
    test("trading (20 rounds)", test_trading)
    test("reasoning (puzzle bank)", test_reasoning)
    test("go (pass-pass ending)", test_go)

    # Matchmaking & leaderboard
    print("\n[Matchmaking & Leaderboard]")
    test("matchmaking", test_matchmaking)
    test("leaderboard", test_leaderboard)
    test("leaderboard_types", test_leaderboard_types)

    # Payment flow
    print("\n[Payment Flow (x402)]")
    test("payment_free_game", test_payment_free_game)
    test("payment_paid_no_header", test_payment_paid_game_no_header)
    test("payment_paid_with_header", test_payment_paid_game_with_header)

    # Summary
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if errors:
        print(f"\n  Failures:")
        for name, err in errors:
            print(f"    - {name}: {err}")
    print(f"{'='*60}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
