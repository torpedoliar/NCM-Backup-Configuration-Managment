from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app_v4.core.auth_service import TokenError

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_events(websocket: WebSocket) -> None:
    runtime = websocket.app.state.runtime
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        claims = runtime.auth_service.verify_access_token(token)
    except TokenError:
        await websocket.close(code=1008)
        return

    await runtime.event_hub.connect(websocket)
    try:
        await runtime.event_hub.send(websocket, "connected", {"user": claims.username, "role": claims.role})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        runtime.event_hub.disconnect(websocket)
