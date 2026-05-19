import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository, hash_refresh_token
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@pytest.mark.asyncio
async def test_login_returns_token_pair(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    password_hash = runtime.auth_service.hash_password("StrongPassword123!")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", password_hash, "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPassword123!"},
        headers={"user-agent": "pytest"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_me_requires_bearer_token(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"c" * 32)
    token = runtime.auth_service.issue_access_token(user_id=1, username="viewer", role="viewer")
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"user_id": 1, "username": "viewer", "role": "viewer"}


@pytest.mark.asyncio
async def test_refresh_rotates_refresh_token(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"h" * 32)
    password_hash = runtime.auth_service.hash_password("StrongPassword123!")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", password_hash, "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPassword123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert refresh_response.status_code == 200
    body = refresh_response.json()
    assert body["access_token"]
    assert body["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"i" * 32)
    password_hash = runtime.auth_service.hash_password("StrongPassword123!")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", password_hash, "admin")
        await session.commit()

    client = TestClient(create_app(runtime))
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "StrongPassword123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

    assert logout_response.status_code == 204
    async with session_factory() as session:
        repo = Repository(session)
        session_row = await repo.get_session_by_refresh_hash(hash_refresh_token(refresh_token))
    assert session_row is not None
    assert session_row.revoked is True
