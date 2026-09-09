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
    async with session_factory() as session:
        await Repository(session).create_user("admin", "h", "admin")
        await session.commit()
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
    # JWT keeps working everywhere it worked before (network-doc is key-only by design;
    # the JWT check below documents that contract rather than changing it).
    for ep in read_endpoints:
        assert client.get(ep, headers=hdr).status_code == 200, ep
    assert client.get("/api/v1/network-doc", headers=hdr).status_code == 401
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


@pytest.mark.asyncio
async def test_write_matrix_scopes(test_settings, session_factory, crypto_service):
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"s" * 32, crypto_service=crypto_service
    )
    async with session_factory() as session:
        await Repository(session).create_user("admin", "h", "admin")
        await session.commit()
    client = TestClient(create_app(runtime))
    hdr = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    def mk(name, scopes):
        r = client.post("/api/v1/api-keys", headers=hdr, json={"name": name, "scopes": scopes})
        assert r.status_code == 201, (name, r.text)
        return {"X-API-Key": r.json()["key"]}

    legacy = mk("legacy", [])
    sw = mk("sw", ["switches:write"])
    cred = mk("cred", ["credentials:write"])
    sched = mk("sched", ["schedules:write"])
    bak = mk("bak", ["backup:write"])

    # bootstrap: 1 credential + 1 switch via JWT
    c = client.post(
        "/api/v1/credentials", headers=hdr, json={"name": "c1", "username": "u", "password": "p"}
    ).json()
    s = client.post(
        "/api/v1/switches",
        headers=hdr,
        json={"name": "s1", "ip": "10.0.0.1", "protocol": "ssh", "port": 22, "credential_id": c["id"]},
    ).json()

    # switches:write opens CRUD; wrong scope and legacy are refused; write key has no read
    assert (
        client.post(
            "/api/v1/switches",
            headers=sw,
            json={"name": "s2", "ip": "10.0.0.2", "protocol": "ssh", "port": 22, "credential_id": c["id"]},
        ).status_code
        == 201
    )
    for bad_key in (cred, sched, legacy):
        assert (
            client.post(
                "/api/v1/switches",
                headers=bad_key,
                json={
                    "name": "sx",
                    "ip": "10.0.0.9",
                    "protocol": "ssh",
                    "port": 22,
                    "credential_id": c["id"],
                },
            ).status_code
            == 403
        )
    assert client.get("/api/v1/switches", headers=sw).status_code == 403
    assert client.patch(f"/api/v1/switches/{s['id']}", headers=sw, json={"notes": "via-dg"}).status_code == 200

    # credentials:write opens set/update with no read-back of secrets
    r = client.post(
        "/api/v1/credentials",
        headers=cred,
        json={"name": "c2", "username": "u2", "password": "SECRET_PW", "enable_password": "SECRET_EN"},
    )
    assert r.status_code == 201
    assert "SECRET_PW" not in r.text and "SECRET_EN" not in r.text
    cid = r.json()["id"]
    r2 = client.patch(f"/api/v1/credentials/{cid}", headers=cred, json={"password": "ROTATED_PW"})
    assert r2.status_code == 200
    assert "ROTATED_PW" not in r2.text
    listed = client.get("/api/v1/credentials", headers=hdr).json()
    assert all("password" not in k for row in listed for k in row.keys())
    assert client.post("/api/v1/credentials", headers=sw, json={"name": "cx", "username": "u", "password": "p"}).status_code == 403

    # schedules:write opens job CRUD; job list opened to read scope in tiket 02
    j = client.post("/api/v1/jobs", headers=sched, json={"switch_id": s["id"], "interval_minutes": 60}).json()
    assert j["id"] > 0
    assert client.patch(f"/api/v1/jobs/{j['id']}", headers=sched, json={"interval_minutes": 30}).status_code == 200
    read = mk("reader", ["read"])
    assert client.get("/api/v1/jobs", headers=read).status_code == 200
    assert client.get("/api/v1/jobs", headers=sched).status_code == 403
    assert (
        client.post("/api/v1/jobs", headers=sw, json={"switch_id": s["id"], "interval_minutes": 60}).status_code == 403
    )
    assert client.delete(f"/api/v1/jobs/{j['id']}", headers=sched).status_code == 204

    # baselines:write enforced (full create path covered by E2E in tiket 07)
    for bad_key in (sw, legacy):
        assert (
            client.post("/api/v1/baselines", headers=bad_key, json={"kind": "switch", "switch_id": s["id"]}).status_code
            == 403
        )
    assert client.get("/api/v1/baselines", headers=read).status_code == 200

    # backup:write opens trigger, other scopes refused; 503 here because the test
    # runtime has no BackupService — auth passed, which is what this matrix asserts.
    t = client.post(f"/api/v1/switches/{s['id']}/backup", headers=bak)
    assert t.status_code in (202, 422, 500, 503), t.text  # never 401/403
    assert client.post(f"/api/v1/switches/{s['id']}/backup", headers=sw).status_code == 403
    assert client.post(f"/api/v1/switches/{s['id']}/backup", headers=legacy).status_code == 403

    # audit recorded for key-based writes (user_id NULL + key name in detail, no secrets)
    async with session_factory() as session:
        audits = await Repository(session).list_audit(limit=50)
    keyed = [a for a in audits if a.detail_json and '"key":"sw"' in a.detail_json]
    assert keyed, "expected audit rows attributed to key 'sw'"
    assert all(a.user_id is None for a in keyed)
