from __future__ import annotations

import httpx


class DesktopApiClient:
    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.client = httpx.AsyncClient(base_url=self.base_url, transport=transport, timeout=15)

    async def login(self, username: str, password: str) -> None:
        response = await self.client.post("/api/v1/auth/login", json={"username": username, "password": password})
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.client.headers["Authorization"] = f"Bearer {self.access_token}"

    async def system_status(self) -> dict:
        response = await self.client.get("/api/v1/system/status")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()
