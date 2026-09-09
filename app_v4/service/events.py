from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket

from app_v4.core.utcdatetime import utc_now

logger = logging.getLogger(__name__)

# Internal event name -> webhook event name(s) (ticket 03). Internal names not
# listed here (backup_started, job_triggered, ...) stay websocket-only.
WEBHOOK_EVENT_MAP: dict[str, tuple[str, ...]] = {
    "backup_failed": ("backup_failed",),
    "backup_completed": ("backup_ok",),
    "config_drift": ("drift", "review_opened"),
    "review_opened": ("review_opened",),
    "review_decided": ("review_decided",),
    "device_offline": ("device_offline",),
}


@dataclass
class EventMessage:
    type: str
    payload: dict[str, Any]
    ts: str

    @classmethod
    def create(cls, event_type: str, payload: dict[str, Any]) -> "EventMessage":
        return cls(type=event_type, payload=payload, ts=utc_now().isoformat() + "Z")


class EventHub:
    def __init__(self, notifier=None):
        self._clients: set[WebSocket] = set()
        self._notifier = notifier

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def send(self, websocket: WebSocket, event_type: str, payload: dict[str, Any]) -> None:
        await websocket.send_json(EventMessage.create(event_type, payload).__dict__)

    async def broadcast(self, event: EventMessage) -> None:
        dead: list[WebSocket] = []
        message = event.__dict__
        for websocket in list(self._clients):
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)
        await self._webhook(event)

    async def _webhook(self, event: EventMessage) -> None:
        """Best-effort webhook fanout — must never break the caller."""
        if self._notifier is None:
            return
        for name in WEBHOOK_EVENT_MAP.get(event.type, ()):
            try:
                await self._notifier.webhook({"type": name, "payload": event.payload, "ts": event.ts})
            except Exception:  # noqa: BLE001 - delivery is best-effort
                logger.warning("webhook fanout failed for %s", name, exc_info=True)


async def publish(hub: EventHub | None, event_type: str, payload: dict[str, Any]) -> None:
    if hub is None:
        return
    await hub.broadcast(EventMessage.create(event_type, payload))
