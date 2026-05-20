import httpx
import pytest

from app_v4.desktop.api_client import DesktopApiClient


@pytest.mark.asyncio
async def test_desktop_api_client_login_sets_tokens():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/login"
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r", "token_type": "bearer"})

    client = DesktopApiClient("http://127.0.0.1:8443", transport=httpx.MockTransport(handler))
    await client.login("admin", "secret")

    assert client.access_token == "a"
    assert client.refresh_token == "r"
    await client.close()
