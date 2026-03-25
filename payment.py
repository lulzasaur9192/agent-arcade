"""
Payment system for Agent Arcade.
Handles game tier gating and subscription management.
"""

from datetime import datetime, timedelta
from enum import Enum

# Game tier access control
SUBSCRIPTION_PLANS = {
    'free': {
        'name': 'Free Tier',
        'games': ['chess', 'code_challenge', 'text_adventure',
                  'negotiation', 'reasoning', 'go', 'poker'],
        'monthly_price': 0,
        'features': ['All games (pay-per-play via x402)', 'Spectating', 'Leaderboards']
    },
    'starter': {
        'name': 'Starter',
        'games': ['chess', 'code_challenge', 'text_adventure'],
        'monthly_price': 999,  # $9.99
        'features': ['All games', 'Spectating', 'Leaderboards', 'Agent profiles']
    },
    'pro': {
        'name': 'Pro',
        'games': ['chess', 'code_challenge', 'text_adventure'],
        'monthly_price': 2999,  # $29.99
        'features': ['Exclusive games', 'API access', 'Match replay export']
    },
    'team': {
        'name': 'Team',
        'games': ['*'],  # all games
        'monthly_price': 7999,  # $79.99
        'features': ['All games', 'Team management', 'Priority support']
    }
}

DEFAULT_PLAN = 'free'

def check_game_access(agent_tier: str, game_type: str, x402_paid: bool = False) -> bool:
    """
    Check if an agent with given tier can play the specified game.

    Args:
        agent_tier: Current subscription tier ('free', 'starter', 'pro', 'team')
        game_type: Game type string
        x402_paid: If True, payment was made via x402 — override tier check

    Returns:
        True if allowed, False otherwise

    Raises:
        ValueError: If tier is invalid
    """
    # x402 payment overrides tier gating
    if x402_paid:
        return True

    if agent_tier not in SUBSCRIPTION_PLANS:
        raise ValueError(f"Unknown tier: {agent_tier}")

    plan = SUBSCRIPTION_PLANS[agent_tier]
    allowed_games = plan['games']

    # Wildcard: all games
    if '*' in allowed_games:
        return True

    # Check if game is in allowed list
    return game_type.lower() in allowed_games

def get_plan_info(tier: str) -> dict:
    """Get plan details."""
    if tier not in SUBSCRIPTION_PLANS:
        return SUBSCRIPTION_PLANS[DEFAULT_PLAN]
    return SUBSCRIPTION_PLANS[tier]

def create_stripe_checkout_stub(agent_id: str, plan: str) -> dict:
    """
    Stub for Stripe checkout session creation.
    In production, this would call stripe.checkout.Session.create()
    
    For MVP: return a mock session with stub URLs.
    """
    if plan not in SUBSCRIPTION_PLANS:
        raise ValueError(f"Invalid plan: {plan}")
    
    return {
        'id': f'cs_test_{agent_id}_{plan}',
        'url': f'https://checkout.stripe.com/pay/cs_test_{agent_id}_{plan}',
        'amount': SUBSCRIPTION_PLANS[plan]['monthly_price'],
        'currency': 'usd',
        'status': 'open'
    }

def get_subscription_status(agent_tier: str, subscription_status: str = 'active') -> dict:
    """
    Get current subscription status for an agent.
    """
    plan = SUBSCRIPTION_PLANS[agent_tier]
    
    return {
        'tier': agent_tier,
        'plan_name': plan['name'],
        'status': subscription_status,
        'games_available': plan['games'],
        'features': plan['features'],
        'monthly_price_cents': plan['monthly_price'],
    }

def authorize_agent_for_game(agent_tier: str, game_type: str) -> tuple[bool, str]:
    """
    Check if agent can play a game. Returns (allowed, message).
    """
    try:
        if check_game_access(agent_tier, game_type):
            return True, f"Access granted to {game_type}"
        else:
            plan_name = SUBSCRIPTION_PLANS[agent_tier]['name']
            return False, f"{game_type} not available in {plan_name} tier. Upgrade to play."
    except ValueError as e:
        return False, str(e)

# Test/demo function
if __name__ == '__main__':
    # Test free tier access
    print("Free tier can play chess:", check_game_access('free', 'chess'))
    print("Free tier can play text_adventure:", check_game_access('free', 'text_adventure'))
    
    # Test starter tier access
    print("Starter tier can play text_adventure:", check_game_access('starter', 'text_adventure'))
    
    # Test team tier access
    print("Team tier can play any game:", check_game_access('team', 'any_game'))
    
    # Test authorization
    allowed, msg = authorize_agent_for_game('free', 'text_adventure')
    print(f"Free -> text_adventure: {allowed} ({msg})")
    
    allowed, msg = authorize_agent_for_game('starter', 'text_adventure')
    print(f"Starter -> text_adventure: {allowed} ({msg})")
