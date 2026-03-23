"""Text Adventure game for Agent Arcade"""
from typing import Optional, List, Dict
import copy
import json

class TextAdventure:
    """Simple text-based dungeon exploration game"""

    ROOMS_TEMPLATE = {
        "entrance": {
            "description": "You stand at the entrance of an ancient dungeon. A narrow passageway leads north.",
            "exits": {"north": "corridor", "south": "exit"},
            "items": ["torch"],
            "npcs": []
        },
        "corridor": {
            "description": "A long corridor with stone walls. Water drips from the ceiling. Paths lead north, south, and east.",
            "exits": {"north": "chamber", "south": "entrance", "east": "treasure_room"},
            "items": ["key"],
            "npcs": ["guard"]
        },
        "chamber": {
            "description": "A large circular chamber. In the center stands a mysterious statue. A door leads south.",
            "exits": {"south": "corridor", "up": "tower"},
            "items": ["ancient_scroll"],
            "npcs": []
        },
        "tower": {
            "description": "The top of a tall tower. You see the exit in the distance. A rope dangles from a hook.",
            "exits": {"down": "chamber", "out": "victory"},
            "items": ["gem"],
            "npcs": []
        },
        "treasure_room": {
            "description": "A small room filled with gold and jewels. A skeleton sits in a chair.",
            "exits": {"west": "corridor"},
            "items": ["treasure_chest"],
            "npcs": ["skeleton"]
        },
        "exit": {
            "description": "You have escaped the dungeon!",
            "exits": {},
            "items": [],
            "npcs": []
        },
        "victory": {
            "description": "Freedom! You've reached the exit and escaped the dungeon!",
            "exits": {},
            "items": [],
            "npcs": []
        }
    }
    
    def __init__(self, game_id: str, player_id: str):
        self.game_id = game_id
        self.player_id = player_id
        self.rooms = copy.deepcopy(self.ROOMS_TEMPLATE)
        self.current_room = "entrance"
        self.inventory = []
        self.move_count = 0
        self.game_over = False
        self.victory = False
        self.move_history = []
    
    def describe_room(self) -> str:
        """Get description of current room"""
        room = self.rooms[self.current_room]
        desc = room["description"] + "\n"
        
        # Add items
        if room["items"]:
            desc += f"\nYou see: {', '.join(room['items'])}\n"
        
        # Add NPCs
        if room["npcs"]:
            desc += f"People here: {', '.join(room['npcs'])}\n"
        
        # Add exits
        exits = list(room["exits"].keys())
        if exits:
            desc += f"Exits: {', '.join(exits)}"
        
        return desc
    
    def process_command(self, command: str) -> Dict:
        """Process a player command"""
        if self.game_over:
            return {'valid': False, 'error': 'Game is over', 'output': ''}
        
        command = command.strip().lower()
        
        # Movement
        if command in self.rooms[self.current_room]["exits"]:
            next_room = self.rooms[self.current_room]["exits"][command]
            self.current_room = next_room
            self.move_count += 1
            self.move_history.append(f"go {command}")
            
            # Check for victory
            if self.current_room in ["exit", "victory"]:
                self.game_over = True
                self.victory = True
                output = self.describe_room() + f"\n\nGame won in {self.move_count} moves!"
            else:
                output = self.describe_room()
            
            return {
                'valid': True,
                'action': 'move',
                'location': self.current_room,
                'output': output,
                'game_over': self.game_over,
                'victory': self.victory
            }
        
        # Take item
        elif command.startswith("take ") or command.startswith("get "):
            item = command.replace("take ", "").replace("get ", "").strip()
            room = self.rooms[self.current_room]
            
            if item in room["items"]:
                self.inventory.append(item)
                room["items"].remove(item)
                self.move_history.append(f"take {item}")
                return {
                    'valid': True,
                    'action': 'take',
                    'item': item,
                    'output': f"You took the {item}.",
                    'inventory': self.inventory
                }
            else:
                return {
                    'valid': False,
                    'error': f"There is no {item} here.",
                    'output': ''
                }
        
        # Check inventory
        elif command in ["inventory", "inv", "i"]:
            return {
                'valid': True,
                'action': 'inventory',
                'output': f"Inventory: {', '.join(self.inventory) if self.inventory else 'empty'}",
                'inventory': self.inventory
            }
        
        # Look around
        elif command in ["look", "l"]:
            return {
                'valid': True,
                'action': 'look',
                'output': self.describe_room()
            }
        
        # Help
        elif command in ["help", "h", "?"]:
            return {
                'valid': True,
                'action': 'help',
                'output': "Commands: move (north/south/east/west), take <item>, inventory, look, help"
            }
        
        else:
            return {
                'valid': False,
                'error': f"Unknown command: {command}",
                'output': "Type 'help' for available commands."
            }
    
    def to_dict(self) -> Dict:
        """Serialize game state"""
        return {
            'game_id': self.game_id,
            'type': 'text_adventure',
            'player_id': self.player_id,
            'current_room': self.current_room,
            'inventory': self.inventory,
            'move_count': self.move_count,
            'game_over': self.game_over,
            'victory': self.victory,
            'move_history': self.move_history,
            'description': self.describe_room(),
            'rooms': {name: {'items': room['items']} for name, room in self.rooms.items()},
        }
