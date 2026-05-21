import pytest
from fastapi.testclient import TestClient

from app_v4.core.runtime_settings import AuthSettings
from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


async def _seed(session_factory, runtime, *, username="operator", password="KnownPass1!", role="operator"):
    password_hash = runtime.auth_service.hash_password(password)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user(username, password_hash, role)
        await session.commit()
    return {"username": username, "password": password}


@pytest.mark.asyncio
async def test_repeated_failures_lock_account(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"l" * 32)
    runtime.auth_settings_provider = lambda: AuthSettings(
        lockout_threshold=3, lockout_window_minutes=10, lockout_duration_minutes=15
    )
    seeded = await _seed(session_factory, runtime)
    client = TestClient(create_app(runtime))
    for _ in range(3):
        r = client.post("/api/v1/auth/login", json={"username": seeded["username"], "password": "wrong"})
        assert r.status_code == 401
    r = client.post(
        "/api/v1/auth/login",
        json={"username": seeded["username"], "password": seeded["password"]},
    )
    assert r.status_code == 423


@pytest.mark.asyncio
async def test_threshold_zero_disables_lockout(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"m" * 32)
    runtime.auth_settings_provider = lambda: AuthSettings(lockout_threshold=0)
    seeded = await _seed(session_factory, runtime)
    client = TestClient(create_app(runtime))
    for _ in range(10):
        r = client.post("/api/v1/auth/login", json={"username": seeded["username"], "password": "wrong"})
        assert r.status_code == 401
    r = client.post(
        "/api/v1/auth/login",
        json={"username": seeded["username"], "password": seeded["password"]},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_successful_login_resets_counter(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"n" * 32)
    seeded = await _seed(session_factory, runtime)
    client = TestClient(create_app(runtime))
    for _ in range(2):
        client.post("/api/v1/auth/login", json={"username": seeded["username"], "password": "wrong"})
    r = client.post(
        "/api/v1/auth/login",
        json={"username": seeded["username"], "password": seeded["password"]},
    )
    assert r.status_code == 200
    for _ in range(2):
        client.post("/api/v1/auth/login", json={"username": seeded["username"], "password": "wrong"})
    r = client.post(
        "/api/v1/auth/login",
        json={"username": seeded["username"], "password": seeded["password"]},
    )
    assert r.status_code == 200
