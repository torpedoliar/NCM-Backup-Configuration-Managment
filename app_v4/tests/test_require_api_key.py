import hashlib

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.deps import require_api_key
from app_v4.service.runtime import ServiceRuntime


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _app(runtime: ServiceRuntime) -> FastAPI:
    app = FastAPI()
    app.state.runtime = runtime

    @app.get("/probe")
    async def probe(name: str = Depends(require_api_key)):
        return {"name": name}

    return app


@pytest.mark.asyncio
async def test_valid_key_passes_case_insensitive_bearer_or_x_api_key(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_api_key(name="netdoc", key_hash=_hash("secret-key"), prefix="ncr_secr")
        await session.commit()

    client = TestClient(_app(runtime))
    bearer_response = client.get("/probe", headers={"Authorization": "bEaReR secret-key"})
    api_key_response = client.get("/probe", headers={"X-API-Key": "secret-key"})

    assert bearer_response.status_code == 200
    assert bearer_response.json() == {"name": "netdoc"}
    assert api_key_response.status_code == 200

    async with session_factory() as session:
        key = await Repository(session).get_api_key_by_hash(_hash("secret-key"))
        assert key is not None and key.last_used_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-API-Key": "wrong"},
        {"Authorization": "Basic secret-key"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer    "},
        {"X-API-Key": "   "},
        {"X-API-Key": "  \t  "},
    ],
)
async def test_missing_bad_or_malformed_key_is_rejected(test_settings, session_factory, headers):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    client = TestClient(_app(runtime))

    response = client.get("/probe", headers=headers)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_revoked_key_is_rejected(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        key = await repo.create_api_key(name="revoked", key_hash=_hash("secret-key"), prefix="ncr_secr")
        await repo.revoke_api_key(key.id)
        await session.commit()

    response = TestClient(_app(runtime)).get("/probe", headers={"X-API-Key": "secret-key"})

    assert response.status_code == 401
