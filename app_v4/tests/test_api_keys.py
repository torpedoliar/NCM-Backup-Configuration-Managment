import hashlib

import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "admin", "admin")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


@pytest.mark.asyncio
async def test_create_lists_and_revoke(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        await Repository(session).create_user("admin", "h", "admin")
        await session.commit()
    client = TestClient(create_app(runtime))
    hdr = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    created = client.post("/api/v1/api-keys", headers=hdr, json={"name": "netdoc"})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "netdoc"
    assert body["key"].startswith("ncr_")

    async with session_factory() as session:
        stored = await Repository(session).get_api_key_by_name("netdoc")
    assert stored is not None
    assert stored.key_hash == hashlib.sha256(body["key"].encode("utf-8")).hexdigest()

    listed = client.get("/api/v1/api-keys", headers=hdr)
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "netdoc"
    assert "key" not in listed.json()[0]
    assert "key_hash" not in listed.json()[0]

    key_id = body["id"]
    assert client.delete(f"/api/v1/api-keys/{key_id}", headers=hdr).status_code == 204

    listed_after_revoke = client.get("/api/v1/api-keys", headers=hdr)
    assert listed_after_revoke.status_code == 200
    assert listed_after_revoke.json()[0]["revoked"] is True


@pytest.mark.asyncio
async def test_duplicate_name_and_absent_key_return_expected_errors(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        await Repository(session).create_user("admin", "h", "admin")
        await session.commit()
    client = TestClient(create_app(runtime))
    hdr = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    assert client.post("/api/v1/api-keys", headers=hdr, json={"name": "netdoc"}).status_code == 201
    assert client.post("/api/v1/api-keys", headers=hdr, json={"name": "netdoc"}).status_code == 409
    assert client.delete("/api/v1/api-keys/999", headers=hdr).status_code == 404


@pytest.mark.asyncio
async def test_viewer_forbidden(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        await Repository(session).create_user("viewer", "h", "viewer")
        await session.commit()
    client = TestClient(create_app(runtime))
    r = client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
        json={"name": "x"},
    )
    assert r.status_code == 403
