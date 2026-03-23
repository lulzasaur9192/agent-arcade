"""Test client for Agent Arcade API"""
import requests
import json

BASE_URL = "http://localhost:5000"

def register_agent(name):
    """Register a new agent"""
    response = requests.post(f"{BASE_URL}/api/agents/register", json={'name': name})
    if response.status_code == 201:
        data = response.json()
        print(f"✓ Registered agent '{name}'")
        print(f"  ID: {data['id']}")
        print(f"  API Key: {data['api_key']}")
        return data
    else:
        print(f"✗ Failed to register: {response.text}")
        return None

def auth_agent(api_key):
    """Authenticate an agent"""
    response = requests.post(f"{BASE_URL}/api/agents/auth", json={'api_key': api_key})
    if response.status_code == 200:
        print(f"✓ Authenticated successfully")
        return response.json()
    else:
        print(f"✗ Auth failed: {response.text}")
        return None

def create_game(player1_id, player2_id):
    """Create a new chess game"""
    response = requests.post(f"{BASE_URL}/api/games/create", json={
        'type': 'chess',
        'player1_id': player1_id,
        'player2_id': player2_id
    })
    if response.status_code == 201:
        data = response.json()
        print(f"✓ Created game {data['id']}")
        return data
    else:
        print(f"✗ Failed to create game: {response.text}")
        return None

def make_move(game_id, player_id, move):
    """Make a move in a game"""
    response = requests.post(f"{BASE_URL}/api/games/{game_id}/move", json={
        'player_id': player_id,
        'move': move
    })
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Move made: {move}")
        return data
    else:
        print(f"✗ Move failed: {response.text}")
        return None

def get_game(game_id):
    """Get game state"""
    response = requests.get(f"{BASE_URL}/api/games/{game_id}")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"✗ Failed to get game: {response.text}")
        return None

def main():
    print("=== Agent Arcade Test Client ===\n")
    
    # Register two agents
    print("1. Registering agents...")
    agent1 = register_agent("AgentAlpha")
    agent2 = register_agent("AgentBeta")
    
    if not agent1 or not agent2:
        print("Failed to register agents")
        return
    
    print()
    
    # Create a game
    print("2. Creating chess game...")
    game = create_game(agent1['id'], agent2['id'])
    if not game:
        return
    
    print()
    
    # Make some moves
    print("3. Making moves...")
    make_move(game['id'], agent1['id'], "e2-e4")
    make_move(game['id'], agent2['id'], "c7-c5")
    make_move(game['id'], agent1['id'], "g1-f3")
    
    print()
    
    # View game state
    print("4. Game state:")
    final_state = get_game(game['id'])
    print(json.dumps(final_state, indent=2))

if __name__ == '__main__':
    main()
