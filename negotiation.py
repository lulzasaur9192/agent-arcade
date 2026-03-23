"""Negotiation game engine for Agent Arcade.

Two agents negotiate over a pool of resources (gold, wood, stone).
Each turn: propose a split or accept/reject the opponent's proposal.
10-round limit with diminishing total value each round.
"""

from typing import Optional


class NegotiationGame:
    """Resource negotiation between two agents."""

    INITIAL_POOL = {"gold": 100, "wood": 200, "stone": 150}
    MAX_ROUNDS = 10
    DECAY_RATE = 0.9  # Pool value multiplied by this each round

    def __init__(self, game_id: str, player1_id: str, player2_id: str):
        self.game_id = game_id
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.current_player = player1_id
        self.round = 1
        self.pool = dict(self.INITIAL_POOL)
        self.current_proposal: Optional[dict] = None
        self.proposer: Optional[str] = None
        self.allocations = {player1_id: {}, player2_id: {}}
        self.game_over = False
        self.winner: Optional[str] = None
        self.reason: Optional[str] = None
        self.move_history: list[dict] = []

    def _pool_value(self) -> float:
        weights = {"gold": 3, "wood": 1, "stone": 2}
        return sum(self.pool[r] * weights[r] for r in self.pool)

    def _allocation_value(self, alloc: dict) -> float:
        weights = {"gold": 3, "wood": 1, "stone": 2}
        return sum(alloc.get(r, 0) * weights.get(r, 0) for r in alloc)

    def _decay_pool(self):
        for r in self.pool:
            self.pool[r] = int(self.pool[r] * self.DECAY_RATE)

    def _switch_player(self):
        self.current_player = (
            self.player2_id if self.current_player == self.player1_id
            else self.player1_id
        )

    def _validate_proposal(self, proposal: dict) -> Optional[str]:
        """Check that a proposal is valid (doesn't exceed pool)."""
        for resource in self.pool:
            p1_share = proposal.get("player1", {}).get(resource, 0)
            p2_share = proposal.get("player2", {}).get(resource, 0)
            if not isinstance(p1_share, (int, float)) or not isinstance(p2_share, (int, float)):
                return f"Shares must be numbers"
            if p1_share < 0 or p2_share < 0:
                return f"Shares cannot be negative"
            if p1_share + p2_share > self.pool[resource]:
                return f"Proposed {resource} ({p1_share}+{p2_share}) exceeds pool ({self.pool[resource]})"
        return None

    def make_move(self, player_id: str, action: str, data: dict = None) -> dict:
        """Process a negotiation move.

        Actions:
          propose: {player1: {gold: N, wood: N, stone: N}, player2: {...}}
          accept:  Accept the current proposal
          reject:  Reject and counter-propose next turn
        """
        if self.game_over:
            return {"valid": False, "error": "Game is over"}
        if player_id != self.current_player:
            return {"valid": False, "error": "Not your turn"}

        data = data or {}

        if action == "propose":
            proposal = data.get("proposal")
            if not proposal:
                return {"valid": False, "error": "proposal required: {player1: {...}, player2: {...}}"}

            err = self._validate_proposal(proposal)
            if err:
                return {"valid": False, "error": err}

            self.current_proposal = proposal
            self.proposer = player_id

            self.move_history.append({
                "round": self.round,
                "player": player_id,
                "action": "propose",
                "proposal": proposal,
            })

            self._switch_player()

            return {
                "valid": True,
                "action": "propose",
                "proposal": proposal,
                "pool": self.pool,
                "round": self.round,
                "game_over": False,
            }

        elif action == "accept":
            if not self.current_proposal:
                return {"valid": False, "error": "No proposal to accept"}

            # Allocate resources
            if self.proposer == self.player1_id:
                self.allocations[self.player1_id] = self.current_proposal.get("player1", {})
                self.allocations[self.player2_id] = self.current_proposal.get("player2", {})
            else:
                self.allocations[self.player1_id] = self.current_proposal.get("player1", {})
                self.allocations[self.player2_id] = self.current_proposal.get("player2", {})

            # Early agreement bonus: remaining rounds as multiplier
            bonus_mult = 1 + (self.MAX_ROUNDS - self.round) * 0.05

            p1_val = self._allocation_value(self.allocations[self.player1_id]) * bonus_mult
            p2_val = self._allocation_value(self.allocations[self.player2_id]) * bonus_mult

            self.game_over = True
            if p1_val > p2_val:
                self.winner = self.player1_id
            elif p2_val > p1_val:
                self.winner = self.player2_id
            else:
                self.winner = None  # draw
            self.reason = f"agreement_round_{self.round}"

            self.move_history.append({
                "round": self.round,
                "player": player_id,
                "action": "accept",
            })

            return {
                "valid": True,
                "action": "accept",
                "allocations": self.allocations,
                "scores": {self.player1_id: p1_val, self.player2_id: p2_val},
                "bonus_multiplier": bonus_mult,
                "game_over": True,
                "winner": self.winner,
                "reason": self.reason,
            }

        elif action == "reject":
            if not self.current_proposal:
                return {"valid": False, "error": "No proposal to reject"}

            self.move_history.append({
                "round": self.round,
                "player": player_id,
                "action": "reject",
            })

            self.current_proposal = None
            self.proposer = None
            self.round += 1
            self._decay_pool()

            if self.round > self.MAX_ROUNDS:
                # No agreement — both get nothing
                self.game_over = True
                self.winner = None
                self.reason = "no_agreement"
                return {
                    "valid": True,
                    "action": "reject",
                    "game_over": True,
                    "winner": None,
                    "reason": "no_agreement",
                    "message": "Negotiation failed — no agreement reached",
                }

            self._switch_player()

            return {
                "valid": True,
                "action": "reject",
                "pool": self.pool,
                "round": self.round,
                "pool_value": self._pool_value(),
                "game_over": False,
                "message": f"Proposal rejected. Round {self.round}, pool decayed.",
            }

        else:
            return {"valid": False, "error": f"Unknown action: {action}. Use propose/accept/reject"}

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "type": "negotiation",
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "current_player": self.current_player,
            "round": self.round,
            "max_rounds": self.MAX_ROUNDS,
            "pool": self.pool,
            "pool_value": self._pool_value(),
            "current_proposal": self.current_proposal,
            "proposer": self.proposer,
            "allocations": self.allocations,
            "game_over": self.game_over,
            "winner": self.winner,
            "reason": self.reason,
            "move_history": self.move_history,
        }
