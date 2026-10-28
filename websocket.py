import json
import asyncio
from fastapi import WebSocket
from datetime import datetime


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.volunteer_connections: dict[str, WebSocket] = {}
        self._location_history: dict[str, list[dict]] = {}

    async def connect(self, websocket: WebSocket, delivery_id: str):
        await websocket.accept()
        if delivery_id not in self.active_connections:
            self.active_connections[delivery_id] = []
        self.active_connections[delivery_id].append(websocket)
        print(f"WebSocket connected for delivery {delivery_id}. Total: {len(self.active_connections[delivery_id])}")

    async def connect_volunteer(self, websocket: WebSocket, volunteer_id: str):
        await websocket.accept()
        self.volunteer_connections[volunteer_id] = websocket
        print(f"Volunteer {volunteer_id} connected via WebSocket")

    def disconnect(self, websocket: WebSocket, delivery_id: str):
        if delivery_id in self.active_connections:
            if websocket in self.active_connections[delivery_id]:
                self.active_connections[delivery_id].remove(websocket)
            if not self.active_connections[delivery_id]:
                del self.active_connections[delivery_id]
        print(f"WebSocket disconnected for delivery {delivery_id}")

    def disconnect_volunteer(self, volunteer_id: str):
        self.volunteer_connections.pop(volunteer_id, None)
        print(f"Volunteer {volunteer_id} disconnected")

    async def broadcast_to_delivery(self, delivery_id: str, message: dict):
        if delivery_id not in self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections[delivery_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        for conn in dead_connections:
            self.active_connections[delivery_id].remove(conn)

    async def send_location_update(self, delivery_id: str, data: dict):
        location_update = {
            "type": "location_update",
            "delivery_id": delivery_id,
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "volunteer_id": data.get("volunteer_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "speed_kmh": data.get("speed_kmh"),
            "heading": data.get("heading"),
        }

        volunteer_id = data.get("volunteer_id")
        if volunteer_id:
            if volunteer_id not in self._location_history:
                self._location_history[volunteer_id] = []
            self._location_history[volunteer_id].append({
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "timestamp": datetime.utcnow().isoformat(),
            })
            if len(self._location_history[volunteer_id]) > 100:
                self._location_history[volunteer_id] = self._location_history[volunteer_id][-100:]

        await self.broadcast_to_delivery(delivery_id, location_update)

    async def send_status_update(self, delivery_id: str, status: str, extra_data: dict | None = None):
        message = {
            "type": "status_update",
            "delivery_id": delivery_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if extra_data:
            message.update(extra_data)
        await self.broadcast_to_delivery(delivery_id, message)

    async def notify_volunteer(self, volunteer_id: str, message: dict):
        ws = self.volunteer_connections.get(volunteer_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.volunteer_connections.pop(volunteer_id, None)

    async def send_to_all_volunteers(self, message: dict):
        dead = []
        for vid, ws in self.volunteer_connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(vid)
        for vid in dead:
            self.volunteer_connections.pop(vid, None)

    def get_location_history(self, volunteer_id: str) -> list[dict]:
        return self._location_history.get(volunteer_id, [])

    def get_delivery_connections_count(self, delivery_id: str) -> int:
        return len(self.active_connections.get(delivery_id, []))

    def get_stats(self) -> dict:
        total_delivery_connections = sum(
            len(conns) for conns in self.active_connections.values()
        )
        return {
            "active_delivery_tracks": len(self.active_connections),
            "total_listeners": total_delivery_connections,
            "connected_volunteers": len(self.volunteer_connections),
        }


ws_manager = ConnectionManager()
