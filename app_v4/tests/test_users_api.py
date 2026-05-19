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
async def test_list_users_requires_admin(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        await repo.create_user("viewer", "h2", "viewer")
        await session.commit()

    client = TestClient(create_app(runtime))
    viewer_resp = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    admin_resp = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert viewer_resp.status_code == 403
    assert admin_resp.status_code == 200
    assert {u["username"] for u in admin_resp.json()} == {"admin", "viewer"}


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_audits(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"username": "ops1", "password": "OpsPass1!", "role": "operator"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "ops1"
    assert body["role"] == "operator"
    assert body["is_active"] is True

    async with session_factory() as session:
        repo = Repository(session)
        created = await repo.get_user_by_username("ops1")
        audits = await repo.list_audit(limit=10)
    assert created is not None
    assert created.password_hash != "OpsPass1!"
    assert any(a.action == "user.create" and a.target_id == str(created.id) for a in audits)


@pytest.mark.asyncio
async def test_update_user_changes_role_and_active(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        target = await repo.create_user("ops1", "h2", "operator")
        await session.commit()
        target_id = target.id

    client = TestClient(create_app(runtime))
    response = client.patch(
        f"/api/v1/users/{target_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"role": "viewer", "is_active": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "viewer"
    assert body["is_active"] is False


@pytest.mark.asyncio
async def test_delete_user_returns_204(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        target = await repo.create_user("ops1", "h2", "operator")
        await session.commit()
        target_id = target.id

    client = TestClient(create_app(runtime))
    response = client.delete(
        f"/api/v1/users/{target_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert response.status_code == 204
    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_user_by_id(target_id) is None
