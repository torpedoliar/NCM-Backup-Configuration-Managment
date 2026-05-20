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
async def test_create_switch(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h", "admin")
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        await session.commit()
        cred_id = cred.id

    client = TestClient(create_app(runtime))
    response = client.post(
        "/api/v1/switches",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={
            "name": "sw01",
            "ip": "10.0.0.1",
            "protocol": "ssh",
            "port": 22,
            "credential_id": cred_id,
            "notes": "rack1",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "sw01"
    assert body["protocol"] == "ssh"
    assert body["credential"]["name"] == "lab"


@pytest.mark.asyncio
async def test_list_switches_visible_to_viewer(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("viewer", "h", "viewer")
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        await repo.create_switch(name="sw01", ip="10.0.0.1", protocol="ssh", port=22, credential_id=cred.id)
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.get(
        "/api/v1/switches",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 200
    assert [s["name"] for s in response.json()] == ["sw01"]


@pytest.mark.asyncio
async def test_update_switch(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h", "admin")
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        sw = await repo.create_switch(name="sw01", ip="10.0.0.1", protocol="ssh", port=22, credential_id=cred.id)
        await session.commit()
        sw_id = sw.id

    client = TestClient(create_app(runtime))
    response = client.patch(
        f"/api/v1/switches/{sw_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"ip": "10.0.0.99", "port": 2222, "notes": "updated"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ip"] == "10.0.0.99"
    assert body["port"] == 2222
    assert body["notes"] == "updated"


@pytest.mark.asyncio
async def test_delete_switch(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h", "admin")
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        sw = await repo.create_switch(name="sw01", ip="10.0.0.1", protocol="ssh", port=22, credential_id=cred.id)
        await session.commit()
        sw_id = sw.id

    client = TestClient(create_app(runtime))
    headers = {"Authorization": f"Bearer {_admin_token(runtime)}"}
    deactivate = client.post(f"/api/v1/switches/{sw_id}/deactivate", headers=headers)
    assert deactivate.status_code == 204

    response = client.delete(f"/api/v1/switches/{sw_id}", headers=headers)

    assert response.status_code == 204
    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_switch(sw_id) is None


async def _seed_switch(session_factory) -> int:
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h", "admin")
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        sw = await repo.create_switch(
            name="sw01", ip="10.0.0.1", protocol="ssh", port=22, credential_id=cred.id
        )
        await session.commit()
        return sw.id


@pytest.mark.asyncio
async def test_deactivate_then_delete_switch(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    sw_id = await _seed_switch(session_factory)

    client = TestClient(create_app(runtime))
    headers = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    r = client.post(f"/api/v1/switches/{sw_id}/deactivate", headers=headers)
    assert r.status_code == 204

    r = client.delete(f"/api/v1/switches/{sw_id}", headers=headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_active_switch_returns_409(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    sw_id = await _seed_switch(session_factory)

    client = TestClient(create_app(runtime))
    headers = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    r = client.delete(f"/api/v1/switches/{sw_id}", headers=headers)
    assert r.status_code == 409
    assert "deactivate" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_switches_excludes_inactive_by_default(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    sw_id = await _seed_switch(session_factory)

    client = TestClient(create_app(runtime))
    headers = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    r = client.post(f"/api/v1/switches/{sw_id}/deactivate", headers=headers)
    assert r.status_code == 204

    r = client.get("/api/v1/switches", headers=headers)
    assert r.status_code == 200
    assert all(sw["id"] != sw_id for sw in r.json())

    r = client.get("/api/v1/switches?include_inactive=true", headers=headers)
    assert r.status_code == 200
    assert any(sw["id"] == sw_id for sw in r.json())


@pytest.mark.asyncio
async def test_activate_switch(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    sw_id = await _seed_switch(session_factory)

    client = TestClient(create_app(runtime))
    headers = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    client.post(f"/api/v1/switches/{sw_id}/deactivate", headers=headers)
    r = client.post(f"/api/v1/switches/{sw_id}/activate", headers=headers)
    assert r.status_code == 204

    r = client.get("/api/v1/switches", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert any(sw["id"] == sw_id for sw in body)
    me = next(sw for sw in body if sw["id"] == sw_id)
    assert me["is_active"] is True
    assert me["deactivated_at"] is None
