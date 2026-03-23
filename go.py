"""Go game engine for Agent Arcade.

9x9 board, standard Go rules: stone placement, capture, ko rule, territory scoring.
Pass mechanic — game ends on double-pass.
Chinese scoring (area counting).
"""

from typing import Optional


class GoGame:
    """9x9 Go game."""

    SIZE = 9
    KOMI = 6.5  # Compensation for white going second

    def __init__(self, game_id: str, player1_id: str, player2_id: str):
        self.game_id = game_id
        self.player1_id = player1_id  # Black
        self.player2_id = player2_id  # White
        self.current_player = player1_id  # Black goes first
        self.board = [[0] * self.SIZE for _ in range(self.SIZE)]  # 0=empty, 1=black, 2=white
        self.move_count = 0
        self.move_history: list[str] = []
        self.captures = {player1_id: 0, player2_id: 0}  # Stones captured
        self.game_over = False
        self.winner: Optional[str] = None
        self.reason: Optional[str] = None
        self.consecutive_passes = 0
        self.ko_point: Optional[tuple[int, int]] = None  # Forbidden point for ko rule
        self.previous_board: Optional[list[list[int]]] = None

    def _player_color(self, player_id: str) -> int:
        return 1 if player_id == self.player1_id else 2

    def _opponent_color(self, color: int) -> int:
        return 3 - color

    @staticmethod
    def parse_move(move_str: str) -> Optional[tuple[int, int]]:
        """Parse move like 'D4' or 'd4' -> (row, col). Also accepts 'pass'."""
        move_str = move_str.strip().lower()
        if move_str == "pass":
            return None  # Signal for pass

        if len(move_str) < 2 or len(move_str) > 3:
            return (-1, -1)  # Invalid

        col_char = move_str[0]
        # Skip 'I' in Go notation
        if col_char < 'a' or col_char > 't' or col_char == 'i':
            if col_char == 'i':
                return (-1, -1)
            return (-1, -1)

        col = ord(col_char) - ord('a')
        if col_char > 'i':
            col -= 1  # Skip I

        try:
            row = int(move_str[1:]) - 1
        except ValueError:
            return (-1, -1)

        return (row, col)

    def _neighbors(self, r: int, c: int) -> list[tuple[int, int]]:
        result = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.SIZE and 0 <= nc < self.SIZE:
                result.append((nr, nc))
        return result

    def _group(self, r: int, c: int) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
        """Find connected group of same-color stones and their liberties."""
        color = self.board[r][c]
        if color == 0:
            return set(), set()

        group = set()
        liberties = set()
        stack = [(r, c)]

        while stack:
            cr, cc = stack.pop()
            if (cr, cc) in group:
                continue
            group.add((cr, cc))
            for nr, nc in self._neighbors(cr, cc):
                if self.board[nr][nc] == 0:
                    liberties.add((nr, nc))
                elif self.board[nr][nc] == color and (nr, nc) not in group:
                    stack.append((nr, nc))

        return group, liberties

    def _remove_group(self, group: set[tuple[int, int]]) -> int:
        """Remove a group of stones from the board. Returns count removed."""
        for r, c in group:
            self.board[r][c] = 0
        return len(group)

    def _copy_board(self) -> list[list[int]]:
        return [row[:] for row in self.board]

    def make_move(self, move_str: str, player_id: str) -> dict:
        if self.game_over:
            return {"valid": False, "error": "Game is over"}
        if player_id != self.current_player:
            return {"valid": False, "error": "Not your turn"}

        color = self._player_color(player_id)
        opp_color = self._opponent_color(color)

        # Pass
        if move_str.strip().lower() == "pass":
            self.consecutive_passes += 1
            self.move_history.append("pass")
            self.move_count += 1
            self.ko_point = None

            if self.consecutive_passes >= 2:
                self._end_game_scoring()
                return {
                    "valid": True,
                    "move": "pass",
                    "board": self.board,
                    "game_over": True,
                    "winner": self.winner,
                    "reason": self.reason,
                    "scores": self._calculate_scores(),
                }

            self._switch_player()
            return {
                "valid": True,
                "move": "pass",
                "board": self.board,
                "game_over": False,
                "consecutive_passes": self.consecutive_passes,
            }

        coords = self.parse_move(move_str)
        if coords is None or coords == (-1, -1):
            return {"valid": False, "error": "Invalid move format. Use letter+number (e.g. D4) or 'pass'"}

        r, c = coords
        if r < 0 or r >= self.SIZE or c < 0 or c >= self.SIZE:
            return {"valid": False, "error": f"Position out of bounds (board is {self.SIZE}x{self.SIZE})"}

        if self.board[r][c] != 0:
            return {"valid": False, "error": "Position already occupied"}

        # Ko rule
        if self.ko_point and (r, c) == self.ko_point:
            return {"valid": False, "error": "Ko rule: cannot recapture immediately"}

        # Save board state for ko detection
        saved_board = self._copy_board()

        # Place stone
        self.board[r][c] = color

        # Capture opponent groups with no liberties
        captured = 0
        for nr, nc in self._neighbors(r, c):
            if self.board[nr][nc] == opp_color:
                group, liberties = self._group(nr, nc)
                if not liberties:
                    captured += self._remove_group(group)

        # Check if placed stone's group has liberties (suicide check)
        own_group, own_liberties = self._group(r, c)
        if not own_liberties:
            # Undo — suicide is not allowed
            self.board = saved_board
            return {"valid": False, "error": "Suicide move not allowed"}

        # Ko detection: if exactly 1 stone captured, set ko point
        if captured == 1:
            # Find the captured position
            for rr in range(self.SIZE):
                for cc in range(self.SIZE):
                    if saved_board[rr][cc] == opp_color and self.board[rr][cc] == 0:
                        # Check if this is a potential ko
                        self.ko_point = (rr, cc)
                        break
                else:
                    continue
                break
        else:
            self.ko_point = None

        # Update captures
        if player_id == self.player1_id:
            self.captures[self.player1_id] += captured
        else:
            self.captures[self.player2_id] += captured

        self.consecutive_passes = 0
        self.previous_board = saved_board
        self.move_history.append(move_str)
        self.move_count += 1

        self._switch_player()

        return {
            "valid": True,
            "move": move_str,
            "board": self.board,
            "captures": dict(self.captures),
            "game_over": False,
        }

    def _switch_player(self):
        self.current_player = (
            self.player2_id if self.current_player == self.player1_id
            else self.player1_id
        )

    def _calculate_scores(self) -> dict:
        """Chinese scoring: stones on board + territory."""
        black_score = 0
        white_score = self.KOMI

        # Count stones on board
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                if self.board[r][c] == 1:
                    black_score += 1
                elif self.board[r][c] == 2:
                    white_score += 1

        # Count territory (empty points surrounded by one color)
        visited = [[False] * self.SIZE for _ in range(self.SIZE)]

        for r in range(self.SIZE):
            for c in range(self.SIZE):
                if self.board[r][c] == 0 and not visited[r][c]:
                    # Flood fill to find territory
                    territory = set()
                    borders = set()  # Colors bordering this territory
                    stack = [(r, c)]

                    while stack:
                        cr, cc = stack.pop()
                        if visited[cr][cc]:
                            continue
                        if self.board[cr][cc] != 0:
                            borders.add(self.board[cr][cc])
                            continue
                        visited[cr][cc] = True
                        territory.add((cr, cc))
                        for nr, nc in self._neighbors(cr, cc):
                            if not visited[nr][nc]:
                                stack.append((nr, nc))

                    # Territory belongs to a color only if bordered by exactly that color
                    if len(borders) == 1:
                        owner = borders.pop()
                        if owner == 1:
                            black_score += len(territory)
                        else:
                            white_score += len(territory)

        return {
            self.player1_id: black_score,
            self.player2_id: white_score,
        }

    def _end_game_scoring(self):
        self.game_over = True
        scores = self._calculate_scores()
        p1_score = scores[self.player1_id]
        p2_score = scores[self.player2_id]

        if p1_score > p2_score:
            self.winner = self.player1_id
        elif p2_score > p1_score:
            self.winner = self.player2_id
        else:
            self.winner = None
        self.reason = f"scoring (B:{p1_score} W:{p2_score})"

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "type": "go",
            "board_size": self.SIZE,
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "current_player": self.current_player,
            "board": self.board,
            "move_count": self.move_count,
            "move_history": self.move_history,
            "captures": self.captures,
            "consecutive_passes": self.consecutive_passes,
            "game_over": self.game_over,
            "winner": self.winner,
            "reason": self.reason,
            "komi": self.KOMI,
        }
