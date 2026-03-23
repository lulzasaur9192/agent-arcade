"""x402 Payment Protocol for Agent Arcade.

HTTP 402 micropayments in USDC via Coinbase x402.
Pay-per-play model — no subscriptions, no accounts needed.

Pricing:
  Chess: FREE
  Code Challenge, Text Adventure: $0.01 USDC
  Negotiation, Trading, Reasoning, Go: $0.02 USDC
  Tournament entry: $0.10 USDC

When X402_WALLET_ADDRESS env var is not set, x402 is disabled (all games free).
"""

import json
import os
from functools import wraps

from flask import request, jsonify

# Game pricing in USDC
GAME_PRICES = {
    "chess": 0,
    "code_challenge": 0.01,
    "text_adventure": 0.01,
    "negotiation": 0.02,
    "trading": 0.02,
    "reasoning": 0.02,
    "go": 0.02,
}

TOURNAMENT_PRICE = 0.10

# Paid endpoints: (method, path_prefix) -> price lookup
PAID_ENDPOINTS = {
    "POST:/api/games/create": "game_type",
    "POST:/api/matchmaking/join": "game_type",
}

# x402 config from env
X402_WALLET_ADDRESS = os.environ.get("X402_WALLET_ADDRESS", "")
X402_NETWORK = os.environ.get("X402_NETWORK", "eip155:8453")  # Base mainnet
X402_FACILITATOR_URL = os.environ.get(
    "X402_FACILITATOR_URL",
    "https://x402.org/facilitator",
)


def x402_enabled() -> bool:
    return bool(X402_WALLET_ADDRESS)


def get_game_price(game_type: str) -> float:
    return GAME_PRICES.get(game_type, 0.02)


def get_pricing_info() -> dict:
    return {
        "payment_protocol": "x402",
        "currency": "USDC",
        "network": X402_NETWORK,
        "enabled": x402_enabled(),
        "games": {
            game: {"price_usdc": price, "free": price == 0}
            for game, price in GAME_PRICES.items()
        },
        "tournament_entry": TOURNAMENT_PRICE,
        "how_it_works": (
            "Send X-PAYMENT header with x402 payment proof. "
            "If no header on a paid game, you get HTTP 402 with payment details."
        ),
    }


def _build_402_response(game_type: str, price: float):
    """Build RFC-compliant 402 Payment Required response."""
    payload = {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "network": X402_NETWORK,
                "maxAmountRequired": str(int(price * 1_000_000)),  # USDC has 6 decimals
                "resource": f"game:{game_type}",
                "description": f"Play {game_type} on Agent Arcade",
                "mimeType": "application/json",
                "payTo": X402_WALLET_ADDRESS,
                "maxTimeoutSeconds": 300,
                "outputSchema": None,
                "extra": {
                    "facilitatorUrl": X402_FACILITATOR_URL,
                    "name": f"Agent Arcade - {game_type}",
                },
            }
        ],
    }
    resp = jsonify(payload)
    resp.status_code = 402
    resp.headers["X-Payment-Required"] = "x402"
    return resp


def _verify_payment(payment_header: str, price: float) -> bool:
    """Verify x402 payment proof.

    In production this calls the facilitator to settle on-chain.
    For now we do basic header presence + structure validation.
    A real deployment would POST to X402_FACILITATOR_URL/verify.
    """
    if not payment_header:
        return False

    try:
        # x402 payments come as base64-encoded JSON or a signed token
        # For MVP: accept any non-empty header when facilitator is not configured
        # Production: call facilitator API to verify + settle
        import base64

        try:
            decoded = base64.b64decode(payment_header)
            payment_data = json.loads(decoded)
            # Check required fields
            if payment_data.get("network") and payment_data.get("payload"):
                return True
        except Exception:
            pass

        # Fallback: if header is present and non-empty, accept for dev/testing
        # Remove this in production
        if len(payment_header) > 10:
            return True

    except Exception:
        pass

    return False


def init_x402(app):
    """Register x402 before_request hook on the Flask app."""

    @app.before_request
    def x402_payment_gate():
        if not x402_enabled():
            # x402 disabled — all games free
            return None

        # Build endpoint key
        endpoint_key = f"{request.method}:{request.path}"

        # Check if this is a paid endpoint
        price_field = None
        for pattern, field in PAID_ENDPOINTS.items():
            method, path = pattern.split(":", 1)
            if request.method == method and request.path == path:
                price_field = field
                break

        if price_field is None:
            return None  # Not a paid endpoint

        # Get game type from request body
        data = request.get_json(silent=True) or {}
        game_type = data.get("type") or data.get("game_type") or data.get(price_field, "")

        price = get_game_price(game_type)

        if price == 0:
            # Free game
            request._x402_paid = False
            return None

        # Check for payment header
        payment_header = request.headers.get("X-PAYMENT", "")

        if not payment_header:
            return _build_402_response(game_type, price)

        # Verify payment
        if _verify_payment(payment_header, price):
            request._x402_paid = True
            return None
        else:
            return jsonify({"error": "Invalid payment proof"}), 400
