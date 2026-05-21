import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "admin", "admin")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


def _operator_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(3, "ops", "operator")


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


@pytest.mark.asyncio
async def test_admin_reset_password_changes_login(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        operator_hash = runtime.auth_service.hash_password("OldPass123!")
        target = await repo.create_user("operator", operator_hash, "operator")
        await session.commit()
        target_id = target.id

    client = TestClient(create_app(runtime))
    response = client.post(
        f"/api/v1/users/{target_id}/password",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"password": "NewPassw0rd!"},
    )
    assert response.status_code == 204

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "NewPassw0rd!"},
    )
    assert login_response.status_code == 200

    async with session_factory() as session:
        repo = Repository(session)
        audits = await repo.list_audit(limit=10)
    assert any(
        a.action == "user.password_reset_by_admin" and a.target_id == str(target_id)
        for a in audits
    )


@pytest.mark.asyncio
async def test_reset_password_admin_only(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("ops", "h1", "operator")
        target = await repo.create_user("operator2", "h2", "operator")
        await session.commit()
        target_id = target.id

    client = TestClient(create_app(runtime))
    response = client.post(
        f"/api/v1/users/{target_id}/password",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
        json={"password": "NewPassw0rd!"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reset_password_too_short_returns_422(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        target = await repo.create_user("op", "h2", "operator")
        await session.commit()
        target_id = target.id

    client = TestClient(create_app(runtime))
    response = client.post(
        f"/api/v1/users/{target_id}/password",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_user_rejects_weak_password(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"username": "newop", "password": "weak", "role": "operator"},
    )
    assert response.status_code == 422
    assert "8" in response.text


@pytest.mark.asyncio
async def test_create_user_rejects_password_missing_required_classes(test_settings, session_factory):
    from app_v4.core.runtime_settings import AuthSettings

    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"u" * 32)
    runtime.auth_settings_provider = lambda: AuthSettings(password_min_length=8)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h1", "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"username": "newop", "password": "alllower1", "role": "operator"},
    )
    assert response.status_code == 422
    assert "upper" in response.text.lower()
