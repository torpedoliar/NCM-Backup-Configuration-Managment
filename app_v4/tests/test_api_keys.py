import hashlib
import json

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.deps import require_api_key
from app_v4.service.runtime import ServiceRuntime


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "admin", "admin")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


def _api_key_probe_app(runtime: ServiceRuntime) -> FastAPI:
    app = FastAPI()
    app.state.runtime = runtime

    @app.get("/probe")
    async def probe(name: str = Depends(require_api_key)):
        return {"name": name}

    return app


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
    probe_client = TestClient(_api_key_probe_app(runtime))
    assert probe_client.get("/probe", headers={"X-API-Key": body["key"]}).status_code == 200
    assert client.delete(f"/api/v1/api-keys/{key_id}", headers=hdr).status_code == 204
    assert probe_client.get("/probe", headers={"X-API-Key": body["key"]}).status_code == 401

    listed_after_revoke = client.get("/api/v1/api-keys", headers=hdr)
    assert listed_after_revoke.status_code == 200
    assert listed_after_revoke.json()[0]["revoked"] is True

    async with session_factory() as session:
        audits = await Repository(session).list_audit(limit=10)
    actions = {audit.action: audit for audit in audits}
    assert {"apikey.created", "apikey.revoked"} <= actions.keys()
    for action in ("apikey.created", "apikey.revoked"):
        audit = actions[action]
        assert audit.target_id == str(key_id)
        assert json.loads(audit.detail_json) == {"name": "netdoc"}
        assert body["key"] not in audit.detail_json
        assert stored.key_hash not in audit.detail_json


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
