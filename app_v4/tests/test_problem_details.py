import pytest
from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_problem_details_media_type_for_http_errors(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory=session_factory, jwt_secret=b"p" * 32)
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/system/status")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 401
