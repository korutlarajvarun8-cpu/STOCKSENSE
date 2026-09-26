"""
WebSocket connection manager for real-time events.
"""
import json
from typing import Dict, List, Set
from fastapi import WebSocket
import asyncio


class ConnectionManager:
    def __init__(self):
        # Map user_id -> list of WebSocket connections
        self._connections: Dict[str, List[WebSocket]] = {}
        # All active connections (for broadcast)
        self._all: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        self._all.append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
        if websocket in self._all:
            self._all.remove(websocket)

    async def send_to_user(self, user_id: str, event: dict):
        """Send event to a specific user (all their connections)."""
        message = json.dumps(event)
        connections = self._connections.get(user_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)

    async def broadcast(self, event: dict):
        """Broadcast event to all connected users."""
        message = json.dumps(event)
        dead = []
        for ws in self._all:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._all.remove(ws)

    def get_connected_count(self) -> int:
        return len(self._all)


# Singleton instance
ws_manager = ConnectionManager()


class EventTypes:
    STOCK_UPDATED = "STOCK_UPDATED"
    RECEIPT_COMPLETED = "RECEIPT_COMPLETED"
    DELIVERY_COMPLETED = "DELIVERY_COMPLETED"
    TRANSFER_COMPLETED = "TRANSFER_COMPLETED"
    ADJUSTMENT_CREATED = "ADJUSTMENT_CREATED"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    EXPIRY_WARNING = "EXPIRY_WARNING"
    NOTIFICATION = "NOTIFICATION"


async def emit_event(event_type: str, data: dict, user_id: str = None):
    """Emit a real-time event."""
    event = {
        "type": event_type,
        "data": data,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    if user_id:
        await ws_manager.send_to_user(user_id, event)
    else:
        await ws_manager.broadcast(event)
