import pytest
from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_websocket_requires_valid_token(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"f" * 32)
    client = TestClient(create_app(runtime))

    try:
        with client.websocket_connect("/ws?token=bad"):
            raise AssertionError("websocket accepted bad token")
    except Exception as exc:
        assert "1008" in str(exc) or "WebSocketDisconnect" in type(exc).__name__


@pytest.mark.asyncio
async def test_websocket_sends_ready_event(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"g" * 32)
    token = runtime.auth_service.issue_access_token(1, "viewer", "viewer")
    client = TestClient(create_app(runtime))

    with client.websocket_connect(f"/ws?token={token}") as websocket:
        data = websocket.receive_json()

    assert data["type"] == "connected"
    assert data["payload"] == {"user": "viewer", "role": "viewer"}
