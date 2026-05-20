import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _operator_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "ops", "operator")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


@pytest.mark.asyncio
async def test_jobs_crud(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"j" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("ops", "hash", "operator")
        await repo.create_user("viewer", "hash", "viewer")
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        switch_id = switch.id

    client = TestClient(create_app(runtime))
    create = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
        json={"switch_id": switch_id, "interval_minutes": 60, "enabled": True, "schedule_hour": 8, "schedule_minute": 30},
    )
    assert create.status_code == 201
    job_id = create.json()["id"]

    list_response = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {_viewer_token(runtime)}"})
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == job_id

    patch = client.patch(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
        json={"interval_minutes": 120, "enabled": False},
    )
    assert patch.status_code == 200
    assert patch.json()["interval_minutes"] == 120
    assert patch.json()["enabled"] is False

    delete = client.delete(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {_operator_token(runtime)}"})
    assert delete.status_code == 204


@pytest.mark.asyncio
async def test_run_job_now_triggers_backup(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"j" * 32)

    called: dict = {}

    class FakeBackupService:
        async def execute_backup(self, switch_id, backup_type, job_id, triggered_by_user_id):
            called.update(
                {
                    "switch_id": switch_id,
                    "backup_type": backup_type,
                    "job_id": job_id,
                    "triggered_by_user_id": triggered_by_user_id,
                }
            )
            return {"success": True, "backup_id": 99, "message": "", "file_path": "", "size_kb": 0}

    runtime.backup_service = FakeBackupService()

    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("ops", "hash", "operator")
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        job = await repo.create_job(switch.id, 60, True, 8, 30)
        await session.commit()
        job_id = job.id
        switch_id = switch.id

    client = TestClient(create_app(runtime))
    response = client.post(
        f"/api/v1/jobs/{job_id}/run",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
    )
    assert response.status_code == 202
    assert called["job_id"] == job_id
    assert called["switch_id"] == switch_id
    assert called["backup_type"] == "manual_schedule"
    body = response.json()
    assert body["backup_id"] == 99
    assert body["success"] is True


@pytest.mark.asyncio
async def test_run_job_now_404_when_missing(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"j" * 32)

    class FakeBackupService:
        async def execute_backup(self, *args, **kwargs):
            raise AssertionError("should not be called")

    runtime.backup_service = FakeBackupService()

    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_user("ops", "hash", "operator")
        await session.commit()

    client = TestClient(create_app(runtime))
    response = client.post(
        "/api/v1/jobs/9999/run",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
    )
    assert response.status_code == 404
