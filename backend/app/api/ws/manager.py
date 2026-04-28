from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: Dict[str, Set[WebSocket]] = {}

    def add(self, room_id: str, websocket: WebSocket) -> None:
        self.rooms.setdefault(room_id, set()).add(websocket)

    def remove(self, room_id: str, websocket: WebSocket) -> None:
        room = self.rooms.get(room_id)
        if room:
            room.discard(websocket)
            if not room:
                del self.rooms[room_id]

    async def broadcast(self, room_id: str, message: str) -> None:
        room = self.rooms.get(room_id, set())
        for ws in list(room):
            try:
                await ws.send_text(message)
            except (WebSocketDisconnect, RuntimeError):
                self.remove(room_id, ws)


manager = ConnectionManager()
