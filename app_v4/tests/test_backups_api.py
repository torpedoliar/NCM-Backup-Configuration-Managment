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


@pytest.mark.asyncio
async def test_trigger_backup_requires_operator(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(
        test_settings,
        session_factory,
        jwt_secret=b"b" * 32,
        backup_service=FakeBackupService({"success": True, "message": "ok", "backup_id": 9, "file_path": "", "size_kb": 1}),
    )
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
