"""Reasoning game engine for Agent Arcade.

Logic puzzle competition — both agents get the same puzzle.
Puzzle types: constraint satisfaction, deduction, pattern matching.
5 puzzles per game, increasing difficulty.
Scoring: correctness (primary) + speed/order (tiebreaker).
"""

import random
from typing import Optional


class ReasoningGame:
    """Logic puzzle competition between two agents."""

    PUZZLE_BANK = [
        # Level 1: Simple pattern
        {
            "level": 1,
            "type": "pattern",
            "prompt": "What comes next in the sequence: 2, 4, 8, 16, ?",
            "answer": "32",
            "accept": ["32"],
            "points": 10,
        },
        {
            "level": 1,
            "type": "pattern",
            "prompt": "What comes next: 1, 1, 2, 3, 5, 8, ?",
            "answer": "13",
            "accept": ["13"],
            "points": 10,
        },
        {
            "level": 1,
            "type": "deduction",
            "prompt": "If all Bloops are Razzles and all Razzles are Lazzles, are all Bloops definitely Lazzles? (yes/no)",
            "answer": "yes",
            "accept": ["yes", "true"],
            "points": 10,
        },
        # Level 2: Medium
        {
            "level": 2,
            "type": "constraint",
            "prompt": "Alice is taller than Bob. Carol is shorter than Bob. Dave is taller than Alice. Who is the shortest?",
            "answer": "Carol",
            "accept": ["carol", "c"],
            "points": 20,
        },
        {
            "level": 2,
            "type": "pattern",
            "prompt": "What comes next: 1, 4, 9, 16, 25, ?",
            "answer": "36",
            "accept": ["36"],
            "points": 20,
        },
        {
            "level": 2,
            "type": "deduction",
            "prompt": "In a room of 3 people, everyone shakes hands once with everyone else. How many handshakes total?",
            "answer": "3",
            "accept": ["3", "three"],
            "points": 20,
        },
        # Level 3: Hard
        {
            "level": 3,
            "type": "constraint",
            "prompt": "3 boxes: one has apples, one has oranges, one has both. All labels are WRONG. You pick one fruit from the box labeled 'Both' and get an apple. What's in the box labeled 'Oranges'?",
            "answer": "Both",
            "accept": ["both", "apples and oranges", "both fruits"],
            "points": 30,
        },
        {
            "level": 3,
            "type": "deduction",
            "prompt": "A bat and ball cost $1.10 total. The bat costs $1.00 more than the ball. How much does the ball cost in cents?",
            "answer": "5",
            "accept": ["5", "5 cents", "$0.05", "0.05"],
            "points": 30,
        },
        {
            "level": 3,
            "type": "pattern",
            "prompt": "What number replaces ?: 3, 3, 5, 4, 4, 3, 5, 5, 4, ?  (Hint: think about word lengths)",
            "answer": "3",
            "accept": ["3", "three"],
            "points": 30,
        },
        # Level 4: Very hard
        {
            "level": 4,
            "type": "constraint",
            "prompt": "5 houses in a row, each a different color. The red house owner drinks coffee. The green house is immediately left of the white house. The green house owner drinks tea. Given these clues, can the middle house be green? (yes/no)",
            "answer": "no",
            "accept": ["no", "false"],
            "points": 40,
        },
        {
            "level": 4,
            "type": "deduction",
            "prompt": "You have 12 coins, one is counterfeit (different weight). Using a balance scale, what is the MINIMUM number of weighings needed to guarantee finding it?",
            "answer": "3",
            "accept": ["3", "three"],
            "points": 40,
        },
        # Level 5: Expert
        {
            "level": 5,
            "type": "constraint",
            "prompt": "Knights always tell truth, Knaves always lie. A says 'We are both Knaves.' What are A and B? (format: A=Knight/Knave, B=Knight/Knave)",
            "answer": "A=Knave, B=Knight",
            "accept": ["a=knave, b=knight", "a=knave b=knight", "knave knight", "a is knave b is knight"],
            "points": 50,
        },
        {
            "level": 5,
            "type": "deduction",
            "prompt": "100 prisoners, 100 boxes each containing a unique number 1-100. Each prisoner may open 50 boxes to find their number. They can strategize beforehand but not communicate during. What is the maximum survival probability using the optimal strategy? (answer as a percentage, nearest whole number)",
            "answer": "31",
            "accept": ["31", "31%", "30", "30%"],
            "points": 50,
        },
    ]

    PUZZLES_PER_GAME = 5

    def __init__(self, game_id: str, player1_id: str, player2_id: str):
        self.game_id = game_id
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.current_player = player1_id
        self.puzzle_index = 0
        self.turn_in_puzzle = 0  # 0 = p1 answers, 1 = p2 answers

        self.scores = {player1_id: 0, player2_id: 0}
        self.game_over = False
        self.winner: Optional[str] = None
        self.reason: Optional[str] = None
        self.move_history: list[dict] = []

        # Select puzzles — one per difficulty level
        rng = random.Random(hash(game_id))
        by_level: dict[int, list] = {}
        for p in self.PUZZLE_BANK:
            by_level.setdefault(p["level"], []).append(p)

        self.puzzles = []
        for level in sorted(by_level.keys()):
            chosen = rng.choice(by_level[level])
            self.puzzles.append(chosen)
            if len(self.puzzles) >= self.PUZZLES_PER_GAME:
                break

        # Pad if fewer levels than PUZZLES_PER_GAME
        while len(self.puzzles) < self.PUZZLES_PER_GAME:
            self.puzzles.append(rng.choice(self.PUZZLE_BANK))

    def current_puzzle(self) -> Optional[dict]:
        if self.puzzle_index < len(self.puzzles):
            p = self.puzzles[self.puzzle_index]
            return {
                "index": self.puzzle_index + 1,
                "total": len(self.puzzles),
                "type": p["type"],
                "prompt": p["prompt"],
                "points": p["points"],
                "level": p["level"],
            }
        return None

    def submit_answer(self, player_id: str, answer: str) -> dict:
        if self.game_over:
            return {"valid": False, "error": "Game is over"}
        if player_id != self.current_player:
            return {"valid": False, "error": "Not your turn"}

        puzzle = self.puzzles[self.puzzle_index]
        normalized = answer.strip().lower()
        correct = normalized in [a.lower() for a in puzzle["accept"]]

        if correct:
            self.scores[player_id] += puzzle["points"]

        self.move_history.append({
            "puzzle": self.puzzle_index + 1,
            "player": player_id,
            "answer": answer,
            "correct": correct,
            "points": puzzle["points"] if correct else 0,
        })

        self.turn_in_puzzle += 1

        if self.turn_in_puzzle >= 2:
            # Both answered — next puzzle
            self.puzzle_index += 1
            self.turn_in_puzzle = 0
            self.current_player = self.player1_id

            if self.puzzle_index >= len(self.puzzles):
                self._end_game()
        else:
            self.current_player = (
                self.player2_id if self.current_player == self.player1_id
                else self.player1_id
            )

        return {
            "valid": True,
            "correct": correct,
            "points_earned": puzzle["points"] if correct else 0,
            "correct_answer": puzzle["answer"] if not correct else None,
            "total_score": self.scores[player_id],
            "puzzle_index": self.puzzle_index,
            "game_over": self.game_over,
            "winner": self.winner,
        }

    def _end_game(self):
        self.game_over = True
        p1_score = self.scores[self.player1_id]
        p2_score = self.scores[self.player2_id]

        if p1_score > p2_score:
            self.winner = self.player1_id
        elif p2_score > p1_score:
            self.winner = self.player2_id
        else:
            self.winner = None  # draw
        self.reason = "all_puzzles_complete"

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "type": "reasoning",
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "current_player": self.current_player,
            "puzzle_index": self.puzzle_index,
            "total_puzzles": len(self.puzzles),
            "current_puzzle": self.current_puzzle(),
            "scores": self.scores,
            "game_over": self.game_over,
            "winner": self.winner,
            "reason": self.reason,
            "move_history": self.move_history,
        }
