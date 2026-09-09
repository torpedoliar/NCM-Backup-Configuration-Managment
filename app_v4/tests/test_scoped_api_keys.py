import json

import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import KNOWN_SCOPES, Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


# ---------- Task 1: model + repository + migration ----------


@pytest.mark.asyncio
async def test_known_scopes_contains_read():
    assert "read" in KNOWN_SCOPES


@pytest.mark.asyncio
async def test_create_key_with_read_scope_persists_normalized(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        key = await repo.create_api_key(
            name="dg", key_hash="h" * 64, prefix="ncr_abcd", scopes=["read", " READ "]
        )
        await session.commit()
        assert json.loads(key.scopes) == ["read"]


@pytest.mark.asyncio
async def test_unknown_scope_raises(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        with pytest.raises(ValueError):
            await repo.create_api_key(name="bad", key_hash="x" * 64, prefix="ncr_bad", scopes=["root"])


@pytest.mark.asyncio
async def test_legacy_key_has_empty_scopes(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        key = await repo.create_api_key(name="legacy", key_hash="y" * 64, prefix="ncr_leg")
        await session.commit()
        assert repo.get_api_key_scopes(key) == []


@pytest.mark.asyncio
async def test_corrupt_scopes_json_reads_as_empty(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        key = await repo.create_api_key(name="corrupt", key_hash="z" * 64, prefix="ncr_cor")
        key.scopes = "{not json"
        await session.commit()
        assert repo.get_api_key_scopes(key) == []


# ---------- Task 2: combined deps + read endpoints matrix ----------


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "admin", "admin")


@pytest.mark.asyncio
async def test_matrix_scope_x_endpoint(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    client = TestClient(create_app(runtime))
    hdr = {"Authorization": f"Bearer {_admin_token(runtime)}"}
    read_key = client.post("/api/v1/api-keys", headers=hdr, json={"name": "dg", "scopes": ["read"]}).json()["key"]
    legacy_key = client.post("/api/v1/api-keys", headers=hdr, json={"name": "legacy"}).json()["key"]

    read_endpoints = ["/api/v1/switches", "/api/v1/backups", "/api/v1/baselines", "/api/v1/reviews"]
    for ep in read_endpoints:
        assert client.get(ep, headers={"X-API-Key": read_key}).status_code == 200, ep
        assert client.get(ep, headers={"X-API-Key": legacy_key}).status_code == 403, ep
    # network-doc regression: legacy key keeps working
    assert client.get("/api/v1/network-doc", headers={"X-API-Key": legacy_key}).status_code == 200
    assert client.get("/api/v1/network-doc", headers={"X-API-Key": read_key}).status_code == 200
    # JWT keeps working everywhere
    for ep in read_endpoints + ["/api/v1/network-doc"]:
        assert client.get(ep, headers=hdr).status_code == 200, ep
    # no credentials at all -> 401
    assert client.get("/api/v1/switches").status_code == 401
    assert client.get("/api/v1/network-doc").status_code == 401


@pytest.mark.asyncio
async def test_create_lists_scopes(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        await Repository(session).create_user("admin", "h", "admin")
        await session.commit()
    client = TestClient(create_app(runtime))
    hdr = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    created = client.post("/api/v1/api-keys", headers=hdr, json={"name": "dg", "scopes": ["read"]})
    assert created.status_code == 201
    assert created.json()["scopes"] == ["read"]

    listed = client.get("/api/v1/api-keys", headers=hdr)
    assert listed.status_code == 200
    assert listed.json()[0]["scopes"] == ["read"]

    bad = client.post("/api/v1/api-keys", headers=hdr, json={"name": "bad", "scopes": ["root"]})
    assert bad.status_code == 422

    legacy = client.post("/api/v1/api-keys", headers=hdr, json={"name": "plain"})
    assert legacy.status_code == 201
    assert legacy.json()["scopes"] == []
