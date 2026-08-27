from fastapi import WebSocket
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps intersection_id to a list of connected WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, intersection_id: str):
        await websocket.accept()
        if intersection_id not in self.active_connections:
            self.active_connections[intersection_id] = []
        self.active_connections[intersection_id].append(websocket)
        logger.info(f"Client connected to {intersection_id}")

    def disconnect(self, websocket: WebSocket, intersection_id: str):
        if intersection_id in self.active_connections:
            if websocket in self.active_connections[intersection_id]:
                self.active_connections[intersection_id].remove(websocket)
            if not self.active_connections[intersection_id]:
                del self.active_connections[intersection_id]
        logger.info(f"Client disconnected from {intersection_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for intersection_id in list(self.active_connections.keys()):
            await self.broadcast_to_intersection(intersection_id, message)

    async def broadcast_to_intersection(self, intersection_id: str, message: str):
        if intersection_id not in self.active_connections:
            return

        dead_connections = []
        for connection in list(self.active_connections.get(intersection_id, [])):
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead, intersection_id)

websocket_manager = ConnectionManager()