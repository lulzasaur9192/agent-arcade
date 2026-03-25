"""Chess game engine for Agent Arcade"""
from typing import List, Tuple, Optional


class ChessGame:
    """Chess game with full move validation including castling and en passant."""

    def __init__(self, game_id: str, player1_id: str, player2_id: str):
        self.game_id = game_id
        self.player1_id = player1_id  # white
        self.player2_id = player2_id  # black
        self.current_player = player1_id
        self.move_count = 0
        self.board = self._init_board()
        self.move_history: list[str] = []
        self.game_over = False
        self.winner: Optional[str] = None
        self.reason: Optional[str] = None

        # Castling rights — lost when king or respective rook moves
        self.white_can_castle_king = True
        self.white_can_castle_queen = True
        self.black_can_castle_king = True
        self.black_can_castle_queen = True

        # En-passant target square (row, col) set after a pawn double-push.
        # Only valid for the very next move.
        self.en_passant_target: Optional[Tuple[int, int]] = None

    # ------------------------------------------------------------------
    # Board setup
    # ------------------------------------------------------------------

    @staticmethod
    def _init_board() -> List[List[Optional[str]]]:
        return [
            ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
            ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
            [None]*8, [None]*8, [None]*8, [None]*8,
            ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
            ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R'],
        ]

    # ------------------------------------------------------------------
    # Parsing / helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_move(move_str: str) -> Optional[Tuple[int, int, int, int]]:
        """Parse coordinate notation e.g. e2-e4 or e2e4."""
        move_str = move_str.replace('-', '').strip().lower()
        if len(move_str) != 4:
            return None
        try:
            from_col = ord(move_str[0]) - ord('a')
            from_row = 8 - int(move_str[1])
            to_col = ord(move_str[2]) - ord('a')
            to_row = 8 - int(move_str[3])
            if not all(0 <= v < 8 for v in (from_row, from_col, to_row, to_col)):
                return None
            return (from_row, from_col, to_row, to_col)
        except (ValueError, IndexError):
            return None

    @staticmethod
    def is_white(piece: Optional[str]) -> bool:
        return piece is not None and piece.isupper()

    @staticmethod
    def is_black(piece: Optional[str]) -> bool:
        return piece is not None and piece.islower()

    def is_white_player(self, player_id: str) -> bool:
        return player_id == self.player1_id

    # ------------------------------------------------------------------
    # Move-validation primitives
    # ------------------------------------------------------------------

    def _path_clear(self, fr: int, fc: int, tr: int, tc: int) -> bool:
        dr = 0 if fr == tr else (1 if tr > fr else -1)
        dc = 0 if fc == tc else (1 if tc > fc else -1)
        r, c = fr + dr, fc + dc
        while (r, c) != (tr, tc):
            if self.board[r][c]:
                return False
            r += dr
            c += dc
        return True

    def _is_valid_move(self, fr: int, fc: int, tr: int, tc: int) -> bool:
        """Check piece-movement rules (no self-check filtering)."""
        piece = self.board[fr][fc]
        if not piece:
            return False

        target = self.board[tr][tc]
        # Can't capture own piece
        if target and self.is_white(piece) == self.is_white(target):
            return False

        pt = piece.lower()
        dr = tr - fr
        dc = tc - fc

        if pt == 'p':
            return self._valid_pawn_move(fr, fc, tr, tc, piece)
        if pt == 'n':
            return (abs(dr) == 2 and abs(dc) == 1) or (abs(dr) == 1 and abs(dc) == 2)
        if pt == 'b':
            return abs(dr) == abs(dc) and dr != 0 and self._path_clear(fr, fc, tr, tc)
        if pt == 'r':
            return (dr == 0 or dc == 0) and (dr != 0 or dc != 0) and self._path_clear(fr, fc, tr, tc)
        if pt == 'q':
            return (dr == 0 or dc == 0 or abs(dr) == abs(dc)) and (dr != 0 or dc != 0) and self._path_clear(fr, fc, tr, tc)
        if pt == 'k':
            if abs(dr) <= 1 and abs(dc) <= 1 and (dr != 0 or dc != 0):
                return True
            # Castling is handled separately in make_move
            return False

        return False

    def _valid_pawn_move(self, fr: int, fc: int, tr: int, tc: int, piece: str) -> bool:
        w = self.is_white(piece)
        direction = -1 if w else 1
        start_row = 6 if w else 1
        dr = tr - fr
        dc = tc - fc
        target = self.board[tr][tc]

        if dc == 0:
            if target:
                return False
            if dr == direction:
                return True
            if fr == start_row and dr == 2 * direction:
                return not self.board[fr + direction][fc]
        elif abs(dc) == 1 and dr == direction:
            # Normal diagonal capture
            if target:
                return True
            # En passant capture
            if (tr, tc) == self.en_passant_target:
                return True
        return False

    # ------------------------------------------------------------------
    # Attack / check helpers
    # ------------------------------------------------------------------

    def _can_attack(self, fr: int, fc: int, tr: int, tc: int, piece: str) -> bool:
        pt = piece.lower()
        dr = tr - fr
        dc = tc - fc
        if pt == 'p':
            pawn_dir = -1 if self.is_white(piece) else 1
            return dr == pawn_dir and abs(dc) == 1
        if pt == 'n':
            return (abs(dr) == 2 and abs(dc) == 1) or (abs(dr) == 1 and abs(dc) == 2)
        if pt == 'b':
            return abs(dr) == abs(dc) and dr != 0 and self._path_clear(fr, fc, tr, tc)
        if pt == 'r':
            return (dr == 0 or dc == 0) and (dr != 0 or dc != 0) and self._path_clear(fr, fc, tr, tc)
        if pt == 'q':
            return (dr == 0 or dc == 0 or abs(dr) == abs(dc)) and (dr != 0 or dc != 0) and self._path_clear(fr, fc, tr, tc)
        if pt == 'k':
            return abs(dr) <= 1 and abs(dc) <= 1 and (dr != 0 or dc != 0)
        return False

    def _is_under_attack(self, r: int, c: int, by_white: bool) -> bool:
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece and self.is_white(piece) == by_white:
                    if self._can_attack(row, col, r, c, piece):
                        return True
        return False

    def _find_king(self, w: bool) -> Tuple[int, int]:
        king = 'K' if w else 'k'
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == king:
                    return (r, c)
        return (-1, -1)

    def _is_in_check(self, w: bool) -> bool:
        kr, kc = self._find_king(w)
        if kr == -1:
            return False
        return self._is_under_attack(kr, kc, not w)

    # ------------------------------------------------------------------
    # Legal-move enumeration (for checkmate / stalemate detection)
    # ------------------------------------------------------------------

    def _has_legal_moves(self, w: bool) -> bool:
        """Return True if the side has at least one legal move."""
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if not piece or self.is_white(piece) != w:
                    continue
                for tr in range(8):
                    for tc in range(8):
                        if (r, c) == (tr, tc):
                            continue
                        if not self._is_valid_move(r, c, tr, tc):
                            continue
                        # Simulate
                        captured = self.board[tr][tc]
                        ep_captured = None
                        # Handle en passant capture in simulation
                        if piece.lower() == 'p' and (tr, tc) == self.en_passant_target and captured is None:
                            ep_row = r  # pawn being captured is on same row
                            ep_captured = self.board[ep_row][tc]
                            self.board[ep_row][tc] = None
                        self.board[tr][tc] = piece
                        self.board[r][c] = None
                        in_check = self._is_in_check(w)
                        # Undo
                        self.board[r][c] = piece
                        self.board[tr][tc] = captured
                        if ep_captured is not None:
                            self.board[r][tc] = ep_captured
                        if not in_check:
                            return True

        # Also check castling moves
        king_row = 7 if w else 0
        if self._can_castle_kingside(w):
            return True
        if self._can_castle_queenside(w):
            return True

        return False

    # ------------------------------------------------------------------
    # Castling
    # ------------------------------------------------------------------

    def _can_castle_kingside(self, w: bool) -> bool:
        if w:
            if not self.white_can_castle_king:
                return False
            row = 7
        else:
            if not self.black_can_castle_king:
                return False
            row = 0

        # King at (row,4), rook at (row,7)
        if self.board[row][4] != ('K' if w else 'k'):
            return False
        if self.board[row][7] != ('R' if w else 'r'):
            return False
        # Squares between must be empty
        if self.board[row][5] or self.board[row][6]:
            return False
        # King must not be in check, pass through check, or land in check
        enemy = not w
        for col in (4, 5, 6):
            if self._is_under_attack(row, col, enemy):
                return False
        return True

    def _can_castle_queenside(self, w: bool) -> bool:
        if w:
            if not self.white_can_castle_queen:
                return False
            row = 7
        else:
            if not self.black_can_castle_queen:
                return False
            row = 0

        if self.board[row][4] != ('K' if w else 'k'):
            return False
        if self.board[row][0] != ('R' if w else 'r'):
            return False
        if self.board[row][1] or self.board[row][2] or self.board[row][3]:
            return False
        enemy = not w
        for col in (4, 3, 2):
            if self._is_under_attack(row, col, enemy):
                return False
        return True

    # ------------------------------------------------------------------
    # Main move entry point
    # ------------------------------------------------------------------

    def make_move(self, move_str: str, player_id: str) -> dict:
        if self.game_over:
            return {'valid': False, 'error': 'Game is over'}
        if player_id != self.current_player:
            return {'valid': False, 'error': 'Not your turn'}

        coords = self.parse_move(move_str)
        if not coords:
            return {'valid': False, 'error': 'Invalid move format (use e2-e4)'}

        fr, fc, tr, tc = coords
        piece = self.board[fr][fc]
        if not piece:
            return {'valid': False, 'error': 'No piece at source square'}

        w = self.is_white(piece)

        # Verify player is moving their own colour
        if w != self.is_white_player(player_id):
            return {'valid': False, 'error': 'Cannot move opponent\'s piece'}

        # --- Castling ---
        if piece.lower() == 'k' and abs(tc - fc) == 2 and fr == tr:
            return self._try_castle(fr, fc, tr, tc, piece, player_id)

        # --- Normal / en-passant move ---
        if not self._is_valid_move(fr, fc, tr, tc):
            return {'valid': False, 'error': 'Illegal move'}

        # Detect en passant capture
        ep_capture = False
        ep_captured_piece = None
        if piece.lower() == 'p' and (tr, tc) == self.en_passant_target and self.board[tr][tc] is None:
            ep_capture = True
            ep_captured_piece = self.board[fr][tc]

        # Apply move
        captured = self.board[tr][tc]
        self.board[tr][tc] = piece
        self.board[fr][fc] = None
        if ep_capture:
            self.board[fr][tc] = None  # remove captured pawn

        # Reject if own king is in check
        if self._is_in_check(w):
            # Undo
            self.board[fr][fc] = piece
            self.board[tr][tc] = captured
            if ep_capture:
                self.board[fr][tc] = ep_captured_piece
            return {'valid': False, 'error': 'Move leaves king in check'}

        # --- Post-move bookkeeping ---

        # Update en passant target
        if piece.lower() == 'p' and abs(tr - fr) == 2:
            self.en_passant_target = ((fr + tr) // 2, fc)
        else:
            self.en_passant_target = None

        # Update castling rights
        self._update_castling_rights(fr, fc, tr, tc, piece)

        # Pawn promotion (auto-queen)
        if piece.lower() == 'p' and (tr == 0 or tr == 7):
            self.board[tr][tc] = 'Q' if w else 'q'

        self.move_history.append(move_str)
        self.move_count += 1

        # Switch player
        self.current_player = (
            self.player2_id if self.current_player == self.player1_id else self.player1_id
        )

        # Check for checkmate / stalemate
        self._check_end_condition(player_id)

        return {
            'valid': True,
            'move': move_str,
            'board': self.board,
            'game_over': self.game_over,
            'winner': self.winner,
            'reason': self.reason,
        }

    def _try_castle(self, fr: int, fc: int, tr: int, tc: int, piece: str, player_id: str) -> dict:
        w = self.is_white(piece)
        kingside = tc > fc

        if kingside:
            if not self._can_castle_kingside(w):
                return {'valid': False, 'error': 'Cannot castle kingside'}
            rook_from, rook_to = 7, 5
        else:
            if not self._can_castle_queenside(w):
                return {'valid': False, 'error': 'Cannot castle queenside'}
            rook_from, rook_to = 0, 3

        row = fr
        rook = self.board[row][rook_from]
        # Move king
        self.board[row][fc] = None
        self.board[row][tc] = piece
        # Move rook
        self.board[row][rook_from] = None
        self.board[row][rook_to] = rook

        # Revoke all castling rights for this side
        if w:
            self.white_can_castle_king = False
            self.white_can_castle_queen = False
        else:
            self.black_can_castle_king = False
            self.black_can_castle_queen = False

        self.en_passant_target = None
        self.move_history.append(f"{chr(fc+ord('a'))}{8-fr}-{chr(tc+ord('a'))}{8-tr}")
        self.move_count += 1

        self.current_player = (
            self.player2_id if self.current_player == self.player1_id else self.player1_id
        )

        self._check_end_condition(player_id)

        return {
            'valid': True,
            'move': f"{'O-O' if kingside else 'O-O-O'}",
            'board': self.board,
            'game_over': self.game_over,
            'winner': self.winner,
            'reason': self.reason,
        }

    def _update_castling_rights(self, fr: int, fc: int, tr: int, tc: int, piece: str) -> None:
        pt = piece.lower()
        # King moved
        if pt == 'k':
            if self.is_white(piece):
                self.white_can_castle_king = False
                self.white_can_castle_queen = False
            else:
                self.black_can_castle_king = False
                self.black_can_castle_queen = False
        # Rook moved or captured
        if pt == 'r' or self.board[tr][tc] is not None:
            # Source rook
            if (fr, fc) == (7, 7):
                self.white_can_castle_king = False
            elif (fr, fc) == (7, 0):
                self.white_can_castle_queen = False
            elif (fr, fc) == (0, 7):
                self.black_can_castle_king = False
            elif (fr, fc) == (0, 0):
                self.black_can_castle_queen = False
            # Destination (rook captured)
            if (tr, tc) == (7, 7):
                self.white_can_castle_king = False
            elif (tr, tc) == (7, 0):
                self.white_can_castle_queen = False
            elif (tr, tc) == (0, 7):
                self.black_can_castle_king = False
            elif (tr, tc) == (0, 0):
                self.black_can_castle_queen = False

    def _check_end_condition(self, last_player_id: str) -> None:
        next_is_white = self.is_white_player(self.current_player)
        if not self._has_legal_moves(next_is_white):
            self.game_over = True
            if self._is_in_check(next_is_white):
                self.winner = last_player_id
                self.reason = 'checkmate'
            else:
                self.reason = 'stalemate'

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            'game_id': self.game_id,
            'type': 'chess',
            'board': self.board,
            'current_player': self.current_player,
            'move_count': self.move_count,
            'move_history': self.move_history,
            'game_over': self.game_over,
            'winner': self.winner,
            'reason': self.reason,
            'en_passant_target': self.en_passant_target,
            'castling': {
                'white_king': self.white_can_castle_king,
                'white_queen': self.white_can_castle_queen,
                'black_king': self.black_can_castle_king,
                'black_queen': self.black_can_castle_queen,
            },
        }
