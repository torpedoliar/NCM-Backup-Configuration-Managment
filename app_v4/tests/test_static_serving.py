import pytest
from fastapi.testclient import TestClient

from app_v4.core.paths import resolve_paths
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_static_index_fallback(test_settings, session_factory):
    static_dir = resolve_paths(test_settings).static_dir
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "index.html").write_text("<div id='root'></div>", encoding="utf-8")

    runtime = ServiceRuntime.for_tests(test_settings, session_factory=session_factory, jwt_secret=b"s" * 32)
    client = TestClient(create_app(runtime))

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "root" in response.text
