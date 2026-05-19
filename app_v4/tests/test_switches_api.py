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
    response = client.delete(
        f"/api/v1/switches/{sw_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert response.status_code == 204
    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_switch(sw_id) is None
