from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


@dataclass
class FakeBackupService:
    result: dict

    async def execute_backup(self, switch_id, backup_type="manual", job_id=None, triggered_by_user_id=None):
        return self.result | {"switch_id": switch_id, "triggered_by_user_id": triggered_by_user_id}


def _operator_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "ops", "operator")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(3, "admin", "admin")


@pytest.mark.asyncio
async def test_trigger_backup_requires_operator(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(
        test_settings,
        session_factory,
        jwt_secret=b"b" * 32,
        backup_service=FakeBackupService({"success": True, "message": "ok", "backup_id": 9, "file_path": "", "size_kb": 1}),
    )
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("ops", "hash", "operator")
        await repo.create_user("viewer", "hash", "viewer")
        await session.commit()

    client = TestClient(create_app(runtime))

    viewer = client.post("/api/v1/switches/1/backups", headers={"Authorization": f"Bearer {_viewer_token(runtime)}"})
    operator = client.post("/api/v1/switches/1/backups", headers={"Authorization": f"Bearer {_operator_token(runtime)}"})

    assert viewer.status_code == 403
    assert operator.status_code == 202
    assert operator.json()["backup_id"] == 9


@pytest.mark.asyncio
async def test_list_and_read_backup_content(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    file_path = tmp_path / "config.txt"
    file_path.write_text("config", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        backup = await repo.create_backup(switch.id, str(file_path), "h", 6, True, "ok")
        await session.commit()
        backup_id = backup.id

    client = TestClient(create_app(runtime))
    list_response = client.get("/api/v1/backups", headers={"Authorization": f"Bearer {_viewer_token(runtime)}"})
    content_response = client.get(f"/api/v1/backups/{backup_id}/content", headers={"Authorization": f"Bearer {_viewer_token(runtime)}"})

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == backup_id
    assert content_response.status_code == 200
    assert content_response.text == "config"


@pytest.mark.asyncio
async def test_list_backups_filters_by_success(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        await repo.create_backup(
            switch.id, "", "h1", 1, success=True, message="ok manual", backup_type="manual"
        )
        await repo.create_backup(
            switch.id, "", "h2", 1, success=False, message="timeout", backup_type="automatic"
        )
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.get(
        "/api/v1/backups?success=true",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert all(b["success"] for b in body)


@pytest.mark.asyncio
async def test_get_backup_content_download_sets_attachment_header(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    file_path = tmp_path / "cfg.txt"
    file_path.write_text("running-config", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("core-sw", "10.0.0.1", "ssh", 22, cred.id)
        backup = await repo.create_backup(switch.id, str(file_path), "h", 14, True, "ok")
        await session.commit()
        backup_id = backup.id

    client = TestClient(create_app(runtime))
    response = client.get(
        f"/api/v1/backups/{backup_id}/content?download=true",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 200
    cd = response.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".txt" in cd
    assert response.text == "running-config"


@pytest.mark.asyncio
async def test_delete_backup_admin_only_and_unlinks_file(test_settings, session_factory, tmp_path: Path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"b" * 32)
    file_path = tmp_path / "cfg.txt"
    file_path.write_text("config", encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("ops", "hash", "operator")
        await repo.create_user("viewer", "hash", "viewer")
        await repo.create_user("admin", "hash", "admin")
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        backup = await repo.create_backup(switch.id, str(file_path), "h", 6, True, "ok")
        await session.commit()
        backup_id = backup.id

    client = TestClient(create_app(runtime))

    forbidden = client.delete(
        f"/api/v1/backups/{backup_id}",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
    )
    assert forbidden.status_code == 403

    deleted = client.delete(
        f"/api/v1/backups/{backup_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )
    assert deleted.status_code == 204
    assert not file_path.exists()

    missing = client.get(
        f"/api/v1/backups/{backup_id}",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )
    assert missing.status_code == 404
