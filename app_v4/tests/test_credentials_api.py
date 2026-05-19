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
async def test_create_credential_encrypts_payload(
    test_settings, session_factory, crypto_service
):
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"k" * 32, crypto_service=crypto_service
    )
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h", "admin")
        await session.commit()
    client = TestClient(create_app(runtime))

    response = client.post(
        "/api/v1/credentials",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={
            "name": "lab-ssh",
            "username": "admin",
            "password": "switchpass",
            "enable_password": "enablepass",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "lab-ssh"
    assert "password" not in body

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.get_credential_by_name("lab-ssh")
        assert cred is not None
        decrypted = crypto_service.decrypt_credential(cred.enc_blob)
    assert decrypted == {
        "username": "admin",
        "password": "switchpass",
        "enable_password": "enablepass",
    }


@pytest.mark.asyncio
async def test_list_credentials_requires_operator_or_admin(
    test_settings, session_factory, crypto_service
):
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"k" * 32, crypto_service=crypto_service
    )
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_credential(name="lab", enc_blob=b"x")
        await session.commit()
    client = TestClient(create_app(runtime))

    viewer_resp = client.get(
        "/api/v1/credentials",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    admin_resp = client.get(
        "/api/v1/credentials",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert viewer_resp.status_code == 403
    assert admin_resp.status_code == 200
    assert [c["name"] for c in admin_resp.json()] == ["lab"]


@pytest.mark.asyncio
async def test_update_credential_re_encrypts(
    test_settings, session_factory, crypto_service
):
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"k" * 32, crypto_service=crypto_service
    )
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("admin", "h", "admin")
        old_blob = crypto_service.encrypt_credential("u", "p", "")
        cred = await repo.create_credential(name="lab", enc_blob=old_blob)
        await session.commit()
        cred_id = cred.id

    client = TestClient(create_app(runtime))
    response = client.patch(
        f"/api/v1/credentials/{cred_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
        json={"username": "u2", "password": "p2", "enable_password": "e2"},
    )

    assert response.status_code == 200
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.get_credential(cred_id)
        decrypted = crypto_service.decrypt_credential(cred.enc_blob)
    assert decrypted == {"username": "u2", "password": "p2", "enable_password": "e2"}


@pytest.mark.asyncio
async def test_delete_credential_in_use_returns_409(
    test_settings, session_factory, crypto_service
):
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"k" * 32, crypto_service=crypto_service
    )
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        await repo.create_switch(
            name="sw01",
            ip="10.0.0.1",
            protocol="ssh",
            port=22,
            credential_id=cred.id,
        )
        await session.commit()
        cred_id = cred.id

    client = TestClient(create_app(runtime))
    response = client.delete(
        f"/api/v1/credentials/{cred_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert response.status_code == 409
