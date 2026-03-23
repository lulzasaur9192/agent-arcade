"""Code Challenge game for Agent Arcade"""
from typing import Optional
import json
import subprocess
import sys
import tempfile
import os


class CodeChallenge:
    """Turn-based code challenge game.

    Players submit Python code that defines a ``solve(input)`` function.
    The function is executed in a sandboxed subprocess against predefined
    test cases with a strict timeout.
    """

    CHALLENGES = {
        "sum_to_n": {
            "title": "Sum to N",
            "description": "Write a function solve(n) that returns the sum of integers from 1 to n.",
            "function": "solve",
            "test_cases": [
                {"input": 5, "expected": 15},
                {"input": 10, "expected": 55},
                {"input": 100, "expected": 5050},
            ],
        },
        "is_palindrome": {
            "title": "Palindrome Check",
            "description": "Write a function solve(s) that returns True if s is a palindrome, False otherwise.",
            "function": "solve",
            "test_cases": [
                {"input": "racecar", "expected": True},
                {"input": "hello", "expected": False},
                {"input": "a", "expected": True},
            ],
        },
        "fibonacci": {
            "title": "Fibonacci",
            "description": "Write a function solve(n) that returns the nth Fibonacci number (0-indexed: fib(0)=0, fib(1)=1, fib(5)=5).",
            "function": "solve",
            "test_cases": [
                {"input": 5, "expected": 5},
                {"input": 10, "expected": 55},
                {"input": 7, "expected": 13},
            ],
        },
    }

    # Seconds before a solution subprocess is killed.
    EXEC_TIMEOUT = 5

    def __init__(self, game_id: str, player1_id: str, player2_id: str, challenge_key: str = "sum_to_n"):
        self.game_id = game_id
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.current_player = player1_id
        self.challenge_key = challenge_key
        self.challenge = self.CHALLENGES.get(challenge_key, self.CHALLENGES["sum_to_n"])
        self.game_over = False
        self.scores = {player1_id: 0, player2_id: 0}
        self.move_history = []
        self.max_rounds = 3
        self.current_round = 0

    # ------------------------------------------------------------------
    # Sandboxed code execution
    # ------------------------------------------------------------------

    @staticmethod
    def _run_code(solution_code: str, test_cases: list, func_name: str, timeout: int) -> dict:
        """Execute *solution_code* in a subprocess and run *test_cases*.

        Returns ``{"passed": int, "failed": int, "results": [...], "error": str|None}``.
        """
        # Build a small harness that imports the user code, runs the tests,
        # and prints results as JSON to stdout.
        harness = _build_harness(solution_code, test_cases, func_name)

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as f:
                f.write(harness)
                tmp_path = f.name

            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                # Trim to last 500 chars to avoid huge tracebacks
                if len(stderr) > 500:
                    stderr = "..." + stderr[-500:]
                return {"passed": 0, "failed": len(test_cases), "results": [], "error": stderr}

            output = json.loads(result.stdout.strip())
            return output

        except subprocess.TimeoutExpired:
            return {
                "passed": 0,
                "failed": len(test_cases),
                "results": [],
                "error": f"Solution timed out after {timeout}s",
            }
        except (json.JSONDecodeError, Exception) as exc:
            return {
                "passed": 0,
                "failed": len(test_cases),
                "results": [],
                "error": str(exc),
            }
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Game interface
    # ------------------------------------------------------------------

    def submit_solution(self, player_id: str, solution_code: str) -> dict:
        """Submit and evaluate a code solution."""
        if self.game_over:
            return {"valid": False, "error": "Game is over"}

        if player_id != self.current_player:
            return {"valid": False, "error": "Not your turn"}

        run = self._run_code(
            solution_code,
            self.challenge["test_cases"],
            self.challenge["function"],
            self.EXEC_TIMEOUT,
        )

        passed = run["passed"]
        failed = run["failed"]
        score = passed
        self.scores[player_id] += score

        self.move_history.append({
            "player": player_id,
            "solution": solution_code[:500],
            "score": score,
            "passed": passed,
            "failed": failed,
            "error": run.get("error"),
            "results": run.get("results", []),
        })

        # Switch to next player
        self.current_player = (
            self.player2_id if self.current_player == self.player1_id else self.player1_id
        )

        # Check if round complete (both players submitted)
        if len(self.move_history) % 2 == 0:
            self.current_round += 1
            if self.current_round >= self.max_rounds:
                self.game_over = True

        return {
            "valid": True,
            "player": player_id,
            "score": score,
            "passed": passed,
            "failed": failed,
            "error": run.get("error"),
            "total_score": self.scores[player_id],
            "game_over": self.game_over,
            "round": self.current_round,
        }

    def get_challenge(self) -> dict:
        return {
            "title": self.challenge["title"],
            "description": self.challenge["description"],
            "test_count": len(self.challenge["test_cases"]),
        }

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "type": "code_challenge",
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "current_player": self.current_player,
            "scores": self.scores,
            "challenge": self.get_challenge(),
            "challenge_key": self.challenge_key,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "game_over": self.game_over,
            "move_history": self.move_history,
            "winner": max(self.scores, key=self.scores.get) if self.game_over else None,
        }


# ----------------------------------------------------------------------
# Harness builder (module-level so it's easy to test)
# ----------------------------------------------------------------------

def _build_harness(solution_code: str, test_cases: list, func_name: str) -> str:
    """Return a self-contained Python script that runs test cases."""
    tests_json = json.dumps(test_cases)
    # The harness forbids imports of os, subprocess, sys, etc. to limit
    # what submitted code can do.  This is a best-effort sandbox — a
    # production system would use a container or WASM runtime.
    return f'''\
import json as _json

# Block dangerous modules
import builtins as _builtins
_ALLOWED_IMPORTS = frozenset([
    "math", "string", "collections", "itertools", "functools",
    "operator", "re", "heapq", "bisect", "array", "decimal",
    "fractions", "random", "copy", "json", "typing",
])
_original_import = _builtins.__import__
def _safe_import(name, *args, **kwargs):
    if name.split(".")[0] not in _ALLOWED_IMPORTS:
        raise ImportError(f"import {{name}} is not allowed")
    return _original_import(name, *args, **kwargs)
_builtins.__import__ = _safe_import

# --- player code ---
{solution_code}
# --- end player code ---

_tests = _json.loads({repr(tests_json)})
_func = globals().get({repr(func_name)})
if not callable(_func):
    print(_json.dumps({{"passed": 0, "failed": len(_tests), "results": [], "error": "No callable {func_name}() found"}}))
    raise SystemExit(0)

_passed = 0
_failed = 0
_results = []
for _t in _tests:
    try:
        _got = _func(_t["input"])
        _ok = _got == _t["expected"]
        if _ok:
            _passed += 1
        else:
            _failed += 1
        _results.append({{"input": _t["input"], "expected": _t["expected"], "got": _got, "pass": _ok}})
    except Exception as _e:
        _failed += 1
        _results.append({{"input": _t["input"], "expected": _t["expected"], "got": None, "pass": False, "error": str(_e)}})

print(_json.dumps({{"passed": _passed, "failed": _failed, "results": _results, "error": None}}))
'''
