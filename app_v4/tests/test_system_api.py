import pytest
from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_system_status_requires_viewer_role(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"d" * 32)
    token = runtime.auth_service.issue_access_token(1, "viewer", "viewer")
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/system/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["service"] == "running"
    assert response.json()["version"] == "4.0.0-dev"


@pytest.mark.asyncio
async def test_system_metrics_requires_auth(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"e" * 32)
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/system/metrics")

    assert response.status_code == 401
