"""Texas Hold'em Poker engine for Agent Arcade.

Heads-up (2-player) Texas Hold'em. 10-hand match — chip leader wins.
1000 starting chips, 10/20 blinds doubling every 4 hands.
"""

import itertools
from typing import Optional


# Card ranks and suits
RANKS = "23456789TJQKA"
SUITS = "shdc"  # spades, hearts, diamonds, clubs
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}

# Hand rankings (higher = better)
HIGH_CARD = 0
ONE_PAIR = 1
TWO_PAIR = 2
THREE_OF_A_KIND = 3
STRAIGHT = 4
FLUSH = 5
FULL_HOUSE = 6
FOUR_OF_A_KIND = 7
STRAIGHT_FLUSH = 8

HAND_NAMES = {
    HIGH_CARD: "High Card",
    ONE_PAIR: "One Pair",
    TWO_PAIR: "Two Pair",
    THREE_OF_A_KIND: "Three of a Kind",
    STRAIGHT: "Straight",
    FLUSH: "Flush",
    FULL_HOUSE: "Full House",
    FOUR_OF_A_KIND: "Four of a Kind",
    STRAIGHT_FLUSH: "Straight Flush",
}


def make_deck():
    """Return a standard 52-card deck as list of 2-char strings."""
    return [r + s for r in RANKS for s in SUITS]


def evaluate_hand(cards):
    """Evaluate a 5-card hand. Returns (rank, tiebreakers) tuple.

    Cards are 2-char strings like 'Ah', 'Tc'.
    Higher tuple = better hand.
    """
    ranks = sorted([RANK_VALUE[c[0]] for c in cards], reverse=True)
    suits = [c[1] for c in cards]

    is_flush = len(set(suits)) == 1

    # Check straight (including A-2-3-4-5 wheel)
    unique_ranks = sorted(set(ranks), reverse=True)
    is_straight = False
    straight_high = 0
    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[4] == 4:
            is_straight = True
            straight_high = unique_ranks[0]
        elif unique_ranks == [12, 3, 2, 1, 0]:  # A-5-4-3-2 wheel
            is_straight = True
            straight_high = 3  # 5-high straight

    # Count rank frequencies
    freq = {}
    for r in ranks:
        freq[r] = freq.get(r, 0) + 1

    counts = sorted(freq.values(), reverse=True)
    # Sort ranks by (frequency desc, rank value desc) for tiebreaking
    ranked_by_freq = sorted(freq.keys(), key=lambda r: (freq[r], r), reverse=True)

    if is_straight and is_flush:
        return (STRAIGHT_FLUSH, straight_high)
    if counts == [4, 1]:
        return (FOUR_OF_A_KIND, ranked_by_freq[0], ranked_by_freq[1])
    if counts == [3, 2]:
        return (FULL_HOUSE, ranked_by_freq[0], ranked_by_freq[1])
    if is_flush:
        return (FLUSH,) + tuple(ranks)
    if is_straight:
        return (STRAIGHT, straight_high)
    if counts == [3, 1, 1]:
        return (THREE_OF_A_KIND, ranked_by_freq[0], ranked_by_freq[1], ranked_by_freq[2])
    if counts == [2, 2, 1]:
        pairs = sorted([r for r, c in freq.items() if c == 2], reverse=True)
        kicker = [r for r, c in freq.items() if c == 1][0]
        return (TWO_PAIR, pairs[0], pairs[1], kicker)
    if counts == [2, 1, 1, 1]:
        pair_rank = [r for r, c in freq.items() if c == 2][0]
        kickers = sorted([r for r, c in freq.items() if c == 1], reverse=True)
        return (ONE_PAIR, pair_rank) + tuple(kickers)
    return (HIGH_CARD,) + tuple(ranks)


def best_hand(cards):
    """Find the best 5-card hand from 7 cards. Returns (rank_tuple, best_5_cards)."""
    best = None
    best_combo = None
    for combo in itertools.combinations(cards, 5):
        score = evaluate_hand(combo)
        if best is None or score > best:
            best = score
            best_combo = combo
    return best, list(best_combo)


class Deck:
    """Seeded deck for reproducible dealing."""

    def __init__(self, seed: int):
        self.seed = seed
        self.cards = make_deck()
        self._rng_state = seed
        self._shuffle()
        self.index = 0

    def _next_rand(self):
        """Simple LCG PRNG for reproducibility."""
        self._rng_state = (self._rng_state * 1103515245 + 12345) & 0x7FFFFFFF
        return self._rng_state

    def _shuffle(self):
        """Fisher-Yates shuffle with seeded RNG."""
        for i in range(len(self.cards) - 1, 0, -1):
            j = self._next_rand() % (i + 1)
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]

    def deal(self, n: int) -> list:
        """Deal n cards from the deck."""
        dealt = self.cards[self.index:self.index + n]
        self.index += n
        return dealt


class PokerGame:
    """Heads-up Texas Hold'em: 10-hand match, chip leader wins."""

    STARTING_CHIPS = 1000
    INITIAL_SMALL_BLIND = 10
    INITIAL_BIG_BLIND = 20
    MAX_HANDS = 10
    BLIND_INCREASE_INTERVAL = 4  # Double blinds every N hands

    PHASES = ["pre_flop", "flop", "turn", "river", "showdown"]

    def __init__(self, game_id: str, player1_id: str, player2_id: str):
        self.game_id = game_id
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.current_player = player1_id  # Overall game state tracking

        # Match state
        self.chips = {player1_id: self.STARTING_CHIPS, player2_id: self.STARTING_CHIPS}
        self.hand_number = 0
        self.dealer = player1_id  # Dealer alternates; in HU, dealer = SB
        self.game_over = False
        self.winner: Optional[str] = None
        self.reason: Optional[str] = None
        self.match_history: list[dict] = []

        # Current hand state
        self.hole_cards = {player1_id: [], player2_id: []}
        self.community_cards: list[str] = []
        self.pot = 0
        self.phase = "waiting"  # waiting, pre_flop, flop, turn, river, showdown
        self.bets = {player1_id: 0, player2_id: 0}
        self.acted_this_round = {player1_id: False, player2_id: False}
        self.folded: Optional[str] = None
        self.all_in: set[str] = set()
        self.hand_history: list[dict] = []

        # Deck state for persistence
        self.deck_seed = 0
        self.deck_index = 0
        self.deck: Optional[Deck] = None

        # Start first hand
        self._start_new_hand()

    def _get_blinds(self):
        """Get current blind levels based on hand number."""
        doublings = self.hand_number // self.BLIND_INCREASE_INTERVAL
        sb = self.INITIAL_SMALL_BLIND * (2 ** doublings)
        bb = self.INITIAL_BIG_BLIND * (2 ** doublings)
        return sb, bb

    def _other_player(self, player_id: str) -> str:
        return self.player2_id if player_id == self.player1_id else self.player1_id

    def _start_new_hand(self):
        """Start a new hand: shuffle, post blinds, deal hole cards."""
        self.hand_number += 1

        # Alternate dealer
        if self.hand_number > 1:
            self.dealer = self._other_player(self.dealer)

        # Create new deck seeded by game_id hash + hand number
        seed = hash(self.game_id) + self.hand_number
        self.deck = Deck(seed)
        self.deck_seed = seed

        # Reset hand state
        self.community_cards = []
        self.pot = 0
        self.folded = None
        self.all_in = set()
        self.hand_history = []
        self.bets = {self.player1_id: 0, self.player2_id: 0}
        self.acted_this_round = {self.player1_id: False, self.player2_id: False}

        sb, bb = self._get_blinds()
        sb_player = self.dealer  # In HU, dealer posts SB
        bb_player = self._other_player(self.dealer)

        # Post blinds (cap at player's remaining chips)
        sb_amount = min(sb, self.chips[sb_player])
        bb_amount = min(bb, self.chips[bb_player])

        self.chips[sb_player] -= sb_amount
        self.chips[bb_player] -= bb_amount
        self.bets[sb_player] = sb_amount
        self.bets[bb_player] = bb_amount
        self.pot = sb_amount + bb_amount

        if sb_amount == self.chips.get(sb_player, 0) + sb_amount:
            # Player went all-in posting blind
            if self.chips[sb_player] == 0:
                self.all_in.add(sb_player)
        if self.chips[bb_player] == 0:
            self.all_in.add(bb_player)

        # Deal hole cards
        self.hole_cards[sb_player] = self.deck.deal(2)
        self.hole_cards[bb_player] = self.deck.deal(2)
        self.deck_index = self.deck.index

        self.phase = "pre_flop"
        # Pre-flop: SB (dealer) acts first in heads-up
        self.current_player = sb_player
        self.acted_this_round = {self.player1_id: False, self.player2_id: False}

        self.hand_history.append({
            "event": "new_hand",
            "hand_number": self.hand_number,
            "dealer": self.dealer,
            "blinds": [sb, bb],
            "chips": dict(self.chips),
        })

    def _betting_round_complete(self) -> bool:
        """Check if the current betting round is complete."""
        p1 = self.player1_id
        p2 = self.player2_id

        # If someone folded, round is over
        if self.folded:
            return True

        # If both are all-in, done
        if p1 in self.all_in and p2 in self.all_in:
            return True

        # If one is all-in and the other has acted, done
        if p1 in self.all_in and self.acted_this_round[p2]:
            return True
        if p2 in self.all_in and self.acted_this_round[p1]:
            return True

        # Both must have acted and bets must be equal
        if self.acted_this_round[p1] and self.acted_this_round[p2]:
            if self.bets[p1] == self.bets[p2]:
                return True

        return False

    def _advance_phase(self):
        """Advance to the next phase and deal community cards."""
        phase_idx = self.PHASES.index(self.phase)
        if phase_idx >= len(self.PHASES) - 1:
            return

        self.phase = self.PHASES[phase_idx + 1]

        if self.phase == "flop":
            self.deck.deal(1)  # burn
            self.community_cards.extend(self.deck.deal(3))
        elif self.phase == "turn":
            self.deck.deal(1)  # burn
            self.community_cards.extend(self.deck.deal(1))
        elif self.phase == "river":
            self.deck.deal(1)  # burn
            self.community_cards.extend(self.deck.deal(1))
        elif self.phase == "showdown":
            self._resolve_showdown()
            return

        self.deck_index = self.deck.index

        # Reset bets and actions for new round
        self.bets = {self.player1_id: 0, self.player2_id: 0}
        self.acted_this_round = {self.player1_id: False, self.player2_id: False}

        # Post-flop: non-dealer acts first
        non_dealer = self._other_player(self.dealer)
        self.current_player = non_dealer

        # If both all-in, auto-advance
        if self.player1_id in self.all_in and self.player2_id in self.all_in:
            self._advance_phase()

    def _resolve_showdown(self):
        """Evaluate hands, award pot, check match end."""
        p1 = self.player1_id
        p2 = self.player2_id

        # Deal remaining community cards if needed (both all-in early)
        while len(self.community_cards) < 5:
            if len(self.community_cards) == 0:
                self.deck.deal(1)  # burn
                self.community_cards.extend(self.deck.deal(3))
            else:
                self.deck.deal(1)  # burn
                self.community_cards.extend(self.deck.deal(1))

        p1_cards = self.hole_cards[p1] + self.community_cards
        p2_cards = self.hole_cards[p2] + self.community_cards

        p1_best, p1_combo = best_hand(p1_cards)
        p2_best, p2_combo = best_hand(p2_cards)

        hand_winner = None
        if p1_best > p2_best:
            hand_winner = p1
        elif p2_best > p1_best:
            hand_winner = p2
        # else: split pot

        if hand_winner:
            self.chips[hand_winner] += self.pot
        else:
            # Split pot
            half = self.pot // 2
            self.chips[p1] += half
            self.chips[p2] += self.pot - half

        self.hand_history.append({
            "event": "showdown",
            "hands": {
                p1: {"cards": self.hole_cards[p1], "best": p1_combo,
                     "rank": HAND_NAMES.get(p1_best[0], "Unknown")},
                p2: {"cards": self.hole_cards[p2], "best": p2_combo,
                     "rank": HAND_NAMES.get(p2_best[0], "Unknown")},
            },
            "community": self.community_cards,
            "pot": self.pot,
            "winner": hand_winner,
        })

        self.match_history.append({
            "hand": self.hand_number,
            "winner": hand_winner,
            "pot": self.pot,
            "showdown": True,
        })

        self._check_match_end()

    def _resolve_fold(self, folder: str):
        """Handle a fold — award pot to opponent."""
        winner = self._other_player(folder)
        self.chips[winner] += self.pot
        self.folded = folder

        self.hand_history.append({
            "event": "fold",
            "player": folder,
            "pot": self.pot,
            "winner": winner,
        })

        self.match_history.append({
            "hand": self.hand_number,
            "winner": winner,
            "pot": self.pot,
            "showdown": False,
        })

        self._check_match_end()

    def _check_match_end(self):
        """Check if match is over (10 hands played or someone busted)."""
        p1 = self.player1_id
        p2 = self.player2_id

        # Someone is busted
        if self.chips[p1] <= 0:
            self.game_over = True
            self.winner = p2
            self.reason = f"{p2} wins — opponent eliminated"
            return
        if self.chips[p2] <= 0:
            self.game_over = True
            self.winner = p1
            self.reason = f"{p1} wins — opponent eliminated"
            return

        # Max hands reached — chip leader wins
        if self.hand_number >= self.MAX_HANDS:
            self.game_over = True
            if self.chips[p1] > self.chips[p2]:
                self.winner = p1
                self.reason = f"{p1} wins with {self.chips[p1]} chips"
            elif self.chips[p2] > self.chips[p1]:
                self.winner = p2
                self.reason = f"{p2} wins with {self.chips[p2]} chips"
            else:
                self.winner = None  # draw
                self.reason = "Tie — equal chips after 10 hands"
            return

        # Start next hand
        self._start_new_hand()

    def make_move(self, player_id: str, action: str, data: dict = None) -> dict:
        """Process a poker action.

        Actions: fold, check, call, raise, all_in
        For raise: data must contain 'amount' (total bet, not raise increment).
        """
        if self.game_over:
            return {"valid": False, "error": "Game is over"}
        if player_id != self.current_player:
            return {"valid": False, "error": "Not your turn"}
        if self.phase in ("waiting", "showdown"):
            return {"valid": False, "error": "No betting in this phase"}
        if player_id in self.all_in:
            return {"valid": False, "error": "You are all-in"}

        data = data or {}
        opponent = self._other_player(player_id)
        my_bet = self.bets[player_id]
        opp_bet = self.bets[opponent]
        to_call = opp_bet - my_bet

        if action == "fold":
            self._resolve_fold(player_id)
            return {
                "valid": True,
                "action": "fold",
                "game_over": self.game_over,
                "winner": self.winner,
                "reason": self.reason,
                "chips": dict(self.chips),
                "hand_number": self.hand_number,
            }

        elif action == "check":
            if to_call > 0:
                return {"valid": False, "error": f"Cannot check — must call {to_call} or fold"}

            self.acted_this_round[player_id] = True
            self.hand_history.append({"event": "check", "player": player_id, "phase": self.phase})

        elif action == "call":
            if to_call <= 0:
                # Nothing to call — treat as check
                self.acted_this_round[player_id] = True
                self.hand_history.append({"event": "check", "player": player_id, "phase": self.phase})
            else:
                call_amount = min(to_call, self.chips[player_id])
                self.chips[player_id] -= call_amount
                self.bets[player_id] += call_amount
                self.pot += call_amount
                self.acted_this_round[player_id] = True

                if self.chips[player_id] == 0:
                    self.all_in.add(player_id)

                self.hand_history.append({
                    "event": "call", "player": player_id,
                    "amount": call_amount, "phase": self.phase,
                })

        elif action == "raise":
            amount = data.get("amount", 0)
            if not isinstance(amount, (int, float)) or amount <= 0:
                return {"valid": False, "error": "raise requires a positive 'amount' (total bet size)"}

            amount = int(amount)
            # Amount is total bet for this round, not increment
            raise_to = amount
            if raise_to <= opp_bet:
                return {"valid": False, "error": f"Raise must be more than current bet of {opp_bet}"}

            additional = raise_to - my_bet
            if additional > self.chips[player_id]:
                return {"valid": False, "error": f"Not enough chips. You have {self.chips[player_id]}, need {additional}"}

            self.chips[player_id] -= additional
            self.bets[player_id] = raise_to
            self.pot += additional
            self.acted_this_round[player_id] = True
            # Opponent must act again after a raise
            self.acted_this_round[opponent] = False

            if self.chips[player_id] == 0:
                self.all_in.add(player_id)

            self.hand_history.append({
                "event": "raise", "player": player_id,
                "amount": raise_to, "phase": self.phase,
            })

        elif action == "all_in":
            all_in_amount = self.chips[player_id]
            self.bets[player_id] += all_in_amount
            self.pot += all_in_amount
            self.chips[player_id] = 0
            self.all_in.add(player_id)
            self.acted_this_round[player_id] = True

            # If this is a raise (more than opponent bet), opponent must act again
            if self.bets[player_id] > opp_bet:
                self.acted_this_round[opponent] = False

            self.hand_history.append({
                "event": "all_in", "player": player_id,
                "amount": all_in_amount, "phase": self.phase,
            })

        else:
            return {"valid": False, "error": f"Unknown action: {action}. Use fold/check/call/raise/all_in"}

        # Check if betting round is complete
        if self._betting_round_complete():
            self._advance_phase()
        else:
            # Switch to opponent
            self.current_player = opponent

        return {
            "valid": True,
            "action": action,
            "phase": self.phase,
            "pot": self.pot,
            "community_cards": self.community_cards,
            "chips": dict(self.chips),
            "hand_number": self.hand_number,
            "game_over": self.game_over,
            "winner": self.winner,
            "reason": self.reason,
        }

    def to_dict(self) -> dict:
        """Full state for persistence."""
        return {
            "game_id": self.game_id,
            "type": "poker",
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "current_player": self.current_player,
            "chips": self.chips,
            "hand_number": self.hand_number,
            "dealer": self.dealer,
            "game_over": self.game_over,
            "winner": self.winner,
            "reason": self.reason,
            "match_history": self.match_history,
            "phase": self.phase,
            "hole_cards": self.hole_cards,
            "community_cards": self.community_cards,
            "pot": self.pot,
            "bets": self.bets,
            "acted_this_round": self.acted_this_round,
            "folded": self.folded,
            "all_in": list(self.all_in),
            "hand_history": self.hand_history,
            "deck_seed": self.deck_seed,
            "deck_index": self.deck.index if self.deck else self.deck_index,
        }

    def to_player_dict(self, player_id: str) -> dict:
        """State visible to a specific player — hides opponent's hole cards."""
        state = self.to_dict()
        opponent = self._other_player(player_id)

        # Mask opponent's hole cards
        masked_hole_cards = dict(self.hole_cards)
        if self.phase != "showdown" and not self.game_over:
            masked_hole_cards[opponent] = ["??", "??"]

        state["hole_cards"] = masked_hole_cards

        # Remove deck internals
        state.pop("deck_seed", None)
        state.pop("deck_index", None)

        return state
