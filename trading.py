"""Trading game engine for Agent Arcade.

Simulated stock market with 5 stocks, 20 trading rounds.
Each agent starts with $10,000 cash.
Prices fluctuate based on agent actions + random market events.
Winner: highest portfolio value at end.
"""

import random
from typing import Optional


class TradingGame:
    """Stock trading simulation between two agents."""

    STOCKS = {
        "ALPHA": {"price": 100.0, "volatility": 0.08},
        "BETA": {"price": 50.0, "volatility": 0.12},
        "GAMMA": {"price": 200.0, "volatility": 0.05},
        "DELTA": {"price": 25.0, "volatility": 0.15},
        "OMEGA": {"price": 75.0, "volatility": 0.10},
    }

    STARTING_CASH = 10000.0
    MAX_ROUNDS = 20

    MARKET_EVENTS = [
        {"name": "Bull Run", "effect": {"all": 0.05}},
        {"name": "Market Crash", "effect": {"all": -0.08}},
        {"name": "Tech Boom", "effect": {"ALPHA": 0.10, "GAMMA": 0.07}},
        {"name": "Commodity Spike", "effect": {"BETA": 0.12, "DELTA": 0.08}},
        {"name": "Sector Rotation", "effect": {"ALPHA": -0.05, "OMEGA": 0.10}},
        {"name": "Quiet Day", "effect": {}},
        {"name": "Earnings Season", "effect": {"GAMMA": 0.06, "OMEGA": -0.04}},
        {"name": "Rate Hike", "effect": {"all": -0.03}},
    ]

    def __init__(self, game_id: str, player1_id: str, player2_id: str):
        self.game_id = game_id
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.current_player = player1_id
        self.round = 1
        self.turn_in_round = 0  # 0 = p1's turn, 1 = p2's turn

        # Stock prices
        self.prices = {s: info["price"] for s, info in self.STOCKS.items()}
        self.volatilities = {s: info["volatility"] for s, info in self.STOCKS.items()}

        # Portfolios
        self.portfolios = {
            player1_id: {"cash": self.STARTING_CASH, "holdings": {s: 0 for s in self.STOCKS}},
            player2_id: {"cash": self.STARTING_CASH, "holdings": {s: 0 for s in self.STOCKS}},
        }

        self.game_over = False
        self.winner: Optional[str] = None
        self.reason: Optional[str] = None
        self.move_history: list[dict] = []
        self.price_history: list[dict] = [dict(self.prices)]
        self.current_event: Optional[dict] = None

        # Seed RNG with game_id for reproducibility
        self._rng = random.Random(hash(game_id))
        self._generate_event()

    def _generate_event(self):
        self.current_event = self._rng.choice(self.MARKET_EVENTS)

    def _apply_market_dynamics(self):
        """Apply random walk + event effects to prices."""
        event = self.current_event or {"effect": {}}
        effects = event.get("effect", {})

        for stock in self.prices:
            # Base random walk
            change = self._rng.gauss(0, self.volatilities[stock])

            # Event effect
            if "all" in effects:
                change += effects["all"]
            if stock in effects:
                change += effects[stock]

            self.prices[stock] = max(1.0, round(self.prices[stock] * (1 + change), 2))

        self.price_history.append(dict(self.prices))
        self._generate_event()

    def _portfolio_value(self, player_id: str) -> float:
        port = self.portfolios[player_id]
        holdings_value = sum(
            port["holdings"][s] * self.prices[s] for s in self.prices
        )
        return round(port["cash"] + holdings_value, 2)

    def make_move(self, player_id: str, actions: list) -> dict:
        """Process trading actions.

        actions: list of {action: "buy"|"sell"|"hold", stock: "ALPHA", quantity: 10}
        """
        if self.game_over:
            return {"valid": False, "error": "Game is over"}
        if player_id != self.current_player:
            return {"valid": False, "error": "Not your turn"}

        if not isinstance(actions, list):
            actions = [actions] if actions else []

        port = self.portfolios[player_id]
        executed = []

        for trade in actions:
            action = trade.get("action", "hold")
            stock = trade.get("stock", "")
            quantity = int(trade.get("quantity", 0))

            if action == "hold":
                executed.append({"action": "hold"})
                continue

            if stock not in self.prices:
                return {"valid": False, "error": f"Unknown stock: {stock}"}
            if quantity <= 0:
                return {"valid": False, "error": "Quantity must be positive"}

            price = self.prices[stock]

            if action == "buy":
                cost = price * quantity
                if cost > port["cash"]:
                    max_qty = int(port["cash"] / price)
                    return {"valid": False, "error": f"Insufficient cash. Max buyable: {max_qty}"}
                port["cash"] -= cost
                port["holdings"][stock] += quantity
                executed.append({"action": "buy", "stock": stock, "quantity": quantity, "price": price, "cost": cost})

            elif action == "sell":
                if port["holdings"][stock] < quantity:
                    return {"valid": False, "error": f"Only hold {port['holdings'][stock]} shares of {stock}"}
                revenue = price * quantity
                port["cash"] += revenue
                port["holdings"][stock] -= quantity
                executed.append({"action": "sell", "stock": stock, "quantity": quantity, "price": price, "revenue": revenue})

            else:
                return {"valid": False, "error": f"Unknown action: {action}. Use buy/sell/hold"}

        port["cash"] = round(port["cash"], 2)

        self.move_history.append({
            "round": self.round,
            "player": player_id,
            "trades": executed,
        })

        self.turn_in_round += 1

        if self.turn_in_round >= 2:
            # Both players traded — advance round
            self._apply_market_dynamics()
            self.round += 1
            self.turn_in_round = 0
            self.current_player = self.player1_id

            if self.round > self.MAX_ROUNDS:
                self._end_game()
        else:
            self._switch_player()

        return {
            "valid": True,
            "trades": executed,
            "portfolio": {
                "cash": port["cash"],
                "holdings": dict(port["holdings"]),
                "total_value": self._portfolio_value(player_id),
            },
            "prices": dict(self.prices),
            "round": min(self.round, self.MAX_ROUNDS),
            "event": self.current_event["name"] if self.current_event else None,
            "game_over": self.game_over,
            "winner": self.winner,
        }

    def _switch_player(self):
        self.current_player = (
            self.player2_id if self.current_player == self.player1_id
            else self.player1_id
        )

    def _end_game(self):
        self.game_over = True
        p1_val = self._portfolio_value(self.player1_id)
        p2_val = self._portfolio_value(self.player2_id)

        if p1_val > p2_val:
            self.winner = self.player1_id
        elif p2_val > p1_val:
            self.winner = self.player2_id
        else:
            self.winner = None
        self.reason = "market_close"

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "type": "trading",
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "current_player": self.current_player,
            "round": min(self.round, self.MAX_ROUNDS),
            "max_rounds": self.MAX_ROUNDS,
            "prices": self.prices,
            "event": self.current_event["name"] if self.current_event else None,
            "portfolios": {
                pid: {
                    "cash": p["cash"],
                    "holdings": dict(p["holdings"]),
                    "total_value": self._portfolio_value(pid),
                }
                for pid, p in self.portfolios.items()
            },
            "game_over": self.game_over,
            "winner": self.winner,
            "reason": self.reason,
            "move_history": self.move_history,
            "price_history": self.price_history,
        }
