"""
WebSocket server for Agent Arcade spectator streaming.

Provides real-time game updates, multi-viewer spectator rooms, and replay
persistence.  When a Flask-SocketIO instance is passed via the ``socketio``
keyword argument, events are emitted over WebSocket to all clients in the
corresponding room (``game_<id>``).  Without it, the manager still works
as a plain data-structure for REST polling.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional


class SpectatorRoom:
    """Spectator room for a single game."""

    def __init__(self, game_id: int):
        self.game_id = game_id
        self.spectators: List[str] = []
        self.move_history: List[dict] = []
        self.board_history: List[str] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.finished = False
        self.winner: Optional[str] = None

    def join_spectator(self, agent_id: str) -> dict:
        if agent_id not in self.spectators:
            self.spectators.append(agent_id)
        return {
            'game_id': self.game_id,
            'spectator_count': len(self.spectators),
            'agent_id': agent_id,
            'status': 'joined',
        }

    def leave_spectator(self, agent_id: str) -> dict:
        if agent_id in self.spectators:
            self.spectators.remove(agent_id)
        return {
            'game_id': self.game_id,
            'spectator_count': len(self.spectators),
            'agent_id': agent_id,
            'status': 'left',
        }

    def record_move(self, move: str, board_state: str):
        entry = {
            'move': move,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'board_state': board_state,
        }
        self.move_history.append(entry)
        self.board_history.append(board_state)
        return entry

    def finish_game(self, winner: str, final_state: str):
        self.finished = True
        self.winner = winner
        if final_state:
            self.board_history.append(final_state)

    def get_replay(self) -> dict:
        return {
            'game_id': self.game_id,
            'created_at': self.created_at,
            'finished': self.finished,
            'winner': self.winner,
            'move_count': len(self.move_history),
            'moves': self.move_history,
            'board_history': self.board_history,
        }


class SpectatorManager:
    """Manages all spectator rooms.

    All public methods accept an optional ``socketio`` keyword so the
    caller can pass in the Flask-SocketIO instance.  If ``None``, no
    WebSocket events are emitted.
    """

    def __init__(self):
        self.rooms: Dict[int, SpectatorRoom] = {}

    def _room_name(self, game_id: int) -> str:
        return f"game_{game_id}"

    def get_or_create_room(self, game_id: int) -> SpectatorRoom:
        if game_id not in self.rooms:
            self.rooms[game_id] = SpectatorRoom(game_id)
        return self.rooms[game_id]

    # -- spectator join / leave ------------------------------------------

    def spectator_join(self, game_id: int, agent_id: str, *, socketio=None) -> dict:
        room = self.get_or_create_room(game_id)
        result = room.join_spectator(agent_id)
        if socketio:
            socketio.emit('spectator_joined', result, to=self._room_name(game_id))
        return result

    def spectator_leave(self, game_id: int, agent_id: str, *, socketio=None) -> dict:
        if game_id not in self.rooms:
            return {'error': 'Game not found'}
        result = self.rooms[game_id].leave_spectator(agent_id)
        if socketio:
            socketio.emit('spectator_left', result, to=self._room_name(game_id))
        return result

    # -- game events -----------------------------------------------------

    def record_game_move(self, game_id: int, move: str, board_state: str, *, socketio=None) -> dict:
        room = self.get_or_create_room(game_id)
        entry = room.record_move(move, board_state)
        event_data = {
            'event': 'move',
            'game_id': game_id,
            'spectator_count': len(room.spectators),
            **entry,
        }
        if socketio:
            socketio.emit('game_move', event_data, to=self._room_name(game_id))
        return event_data

    def finish_game(self, game_id: int, winner: str, final_state: str, *, socketio=None) -> dict:
        room = self.get_or_create_room(game_id)
        room.finish_game(winner, final_state)
        event_data = {
            'event': 'game_finished',
            'game_id': game_id,
            'winner': winner,
            'final_state': final_state,
            'spectator_count': len(room.spectators),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        if socketio:
            socketio.emit('game_finished', event_data, to=self._room_name(game_id))
        return event_data

    # -- queries ---------------------------------------------------------

    def get_spectator_count(self, game_id: int) -> int:
        if game_id not in self.rooms:
            return 0
        return len(self.rooms[game_id].spectators)

    def get_replay(self, game_id: int) -> Optional[dict]:
        if game_id not in self.rooms:
            return None
        return self.rooms[game_id].get_replay()

    def get_active_games(self) -> List[dict]:
        return [
            {
                'game_id': game_id,
                'spectator_count': len(room.spectators),
                'finished': room.finished,
            }
            for game_id, room in self.rooms.items()
            if len(room.spectators) > 0 or not room.finished
        ]


# Global instance
spectator_manager = SpectatorManager()
