from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import WebSocket


@dataclass
class EventMessage:
    type: str
    payload: dict[str, Any]
    ts: str


class EventHub:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def send(self, websocket: WebSocket, event_type: str, payload: dict[str, Any]) -> None:
        await websocket.send_json(self._message(event_type, payload).__dict__)

    async def broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        message = self._message(event_type, payload).__dict__
        for websocket in list(self._clients):
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)

    def _message(self, event_type: str, payload: dict[str, Any]) -> EventMessage:
        return EventMessage(type=event_type, payload=payload, ts=datetime.utcnow().isoformat() + "Z")
