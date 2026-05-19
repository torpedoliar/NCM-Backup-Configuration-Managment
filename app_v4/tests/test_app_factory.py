import pytest
from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_app_factory_exposes_openapi(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory=session_factory, jwt_secret=b"a" * 32)
    app = create_app(runtime)
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "NCM v4 Backend"
