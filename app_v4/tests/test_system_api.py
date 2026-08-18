import pytest
from fastapi.testclient import TestClient

from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "viewer", "viewer")


def _operator_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "ops", "operator")


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(3, "admin", "admin")


class _StubScheduler:
    def __init__(self) -> None:
        self.last_id: str | None = None
        self.last_trigger = None

    def get_job(self, job_id: str):
        return object()

    def reschedule_job(self, job_id: str, trigger) -> None:
        self.last_id = job_id
        self.last_trigger = trigger


class _StubSchedulerService:
    def __init__(self) -> None:
        self.scheduler = _StubScheduler()

    def reschedule_retention(self, hour: int, minute: int) -> None:
        from apscheduler.triggers.cron import CronTrigger
        self.scheduler.reschedule_job(
            "retention-nightly", CronTrigger(hour=hour, minute=minute)
        )


@pytest.mark.asyncio
async def test_system_status_requires_viewer_role(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"d" * 32)
    token = runtime.auth_service.issue_access_token(1, "viewer", "viewer")
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/system/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["service"] == "running"
    assert response.json()["version"] == "4.6.0"


@pytest.mark.asyncio
async def test_system_metrics_requires_auth(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"e" * 32)
    client = TestClient(create_app(runtime))

    response = client.get("/api/v1/system/metrics")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_retention_returns_defaults(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"f" * 32)
    client = TestClient(create_app(runtime))
    response = client.get(
        "/api/v1/system/retention",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["backup_retention_days"] == 365
    assert data["retention_hour"] == 3


@pytest.mark.asyncio
async def test_patch_retention_admin_only(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"g" * 32)
    client = TestClient(create_app(runtime))
    response = client.patch(
        "/api/v1/system/retention",
        json={"backup_retention_days": 30},
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_patch_retention_validates_ranges(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"h" * 32)
    client = TestClient(create_app(runtime))
    response = client.patch(
        "/api/v1/system/retention",
        json={"backup_retention_days": 1},
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_retention_persists_and_reschedules(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"i" * 32)
    runtime.scheduler_service = _StubSchedulerService()
    from app_v4.data.repository import Repository
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id
    admin_token = runtime.auth_service.issue_access_token(admin_id, "admin", "admin")
    client = TestClient(create_app(runtime))
    response = client.patch(
        "/api/v1/system/retention",
        json={"retention_hour": 5, "retention_minute": 30},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    # Verify file persisted
    from app_v4.core.paths import resolve_paths
    from app_v4.core.runtime_settings import load_runtime_settings
    paths = resolve_paths(runtime.settings)
    persisted = load_runtime_settings(paths.data_dir / "runtime_settings.json")
    assert persisted.retention.retention_hour == 5
    assert persisted.retention.retention_minute == 30

    # Verify scheduler reschedule call
    trigger = runtime.scheduler_service.scheduler.last_trigger
    assert runtime.scheduler_service.scheduler.last_id == "retention-nightly"
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields["hour"] == "5"
    assert fields["minute"] == "30"


@pytest.mark.asyncio
async def test_status_returns_paths(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"j" * 32)
    client = TestClient(create_app(runtime))
    response = client.get(
        "/api/v1/system/status",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "data_dir" in payload and "backups_dir" in payload and "logs_dir" in payload


@pytest.mark.asyncio
async def test_get_auth_settings_admin_only(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"k" * 32)
    client = TestClient(create_app(runtime))
    r = client.get(
        "/api/v1/system/auth-settings",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    assert r.status_code == 403
    r = client.get(
        "/api/v1/system/auth-settings",
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token_minutes"] == 15
    assert body["lockout_threshold"] == 5
    assert body["password_min_length"] == 8


@pytest.mark.asyncio
async def test_patch_auth_settings_persists_and_validates(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"l" * 32)
    from app_v4.data.repository import Repository
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id
    admin_token = runtime.auth_service.issue_access_token(admin_id, "admin", "admin")
    client = TestClient(create_app(runtime))
    r = client.patch(
        "/api/v1/system/auth-settings",
        json={"access_token_minutes": 4},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422

    r = client.patch(
        "/api/v1/system/auth-settings",
        json={"access_token_minutes": 30, "lockout_threshold": 0},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token_minutes"] == 30
    assert body["lockout_threshold"] == 0


@pytest.mark.asyncio
async def test_get_backup_location_returns_resolved_path(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"n" * 32)
    client = TestClient(create_app(runtime))

    response = client.get(
        "/api/v1/system/backup-location",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["backup_root_folder"] == "backups"
    assert body["resolved_backups_dir"].endswith("backups")


@pytest.mark.asyncio
async def test_patch_backup_location_admin_only(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"o" * 32)
    client = TestClient(create_app(runtime))

    response = client.patch(
        "/api/v1/system/backup-location",
        json={"backup_root_folder": "custom-backups"},
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_patch_backup_location_persists_and_updates_runtime(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"p" * 32)
    from app_v4.data.repository import Repository
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id
    admin_token = runtime.auth_service.issue_access_token(admin_id, "admin", "admin")
    client = TestClient(create_app(runtime))

    response = client.patch(
        "/api/v1/system/backup-location",
        json={"backup_root_folder": "custom-backups"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["backup_root_folder"] == "custom-backups"
    assert body["resolved_backups_dir"].endswith("custom-backups")
    assert runtime.settings.backup_root_folder == "custom-backups"

    from app_v4.core.paths import resolve_paths
    from app_v4.core.runtime_settings import load_runtime_settings
    persisted = load_runtime_settings(resolve_paths(runtime.settings).data_dir / "runtime_settings.json")
    assert persisted.backup_location.backup_root_folder == "custom-backups"


@pytest.mark.asyncio
async def test_patch_backup_location_validates_value(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"q" * 32)
    client = TestClient(create_app(runtime))

    response = client.patch(
        "/api/v1/system/backup-location",
        json={"backup_root_folder": ""},
        headers={"Authorization": f"Bearer {_admin_token(runtime)}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_logs_endpoint_admin_only(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"M" * 32)
    client = TestClient(create_app(runtime))
    r = client.get(
        "/api/v1/system/logs",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_logs_endpoint_returns_recent_lines(test_settings, session_factory, tmp_path, monkeypatch):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"L" * 32)
    from app_v4.data.repository import Repository
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id
    admin_token = runtime.auth_service.issue_access_token(admin_id, "admin", "admin")

    log_file = tmp_path / "ncm-v4.log"
    log_file.write_text(
        "2026-05-20 10:00:00 INFO     uvicorn.error: started\n"
        "2026-05-20 10:00:01 WARNING  uvicorn.error: slow disk\n"
        "2026-05-20 10:00:02 ERROR    uvicorn.error: failed conn\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app_v4.service.api.system._resolve_log_file", lambda runtime: log_file)

    client = TestClient(create_app(runtime))
    r = client.get(
        "/api/v1/system/logs?level=ERROR",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert all(line["level"] == "ERROR" for line in body["lines"])
    assert body["log_file"].endswith("ncm-v4.log")
    assert body["log_file_size_bytes"] > 0


@pytest.mark.asyncio
async def test_get_time_settings_default_jakarta(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"T" * 32)
    client = TestClient(create_app(runtime))
    r = client.get(
        "/api/v1/system/time-settings",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["timezone"] == "Asia/Jakarta"
    assert "Asia/Jakarta" in body["available_timezones"]
    assert body["ntp_servers"] == ["pool.ntp.org"]


@pytest.mark.asyncio
async def test_patch_time_settings_admin_only_and_persists(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"T" * 32)
    from app_v4.data.repository import Repository
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id
    admin_token = runtime.auth_service.issue_access_token(admin_id, "admin", "admin")

    client = TestClient(create_app(runtime))

    forbidden = client.patch(
        "/api/v1/system/time-settings",
        json={"timezone": "Asia/Tokyo"},
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
    )
    assert forbidden.status_code == 403

    r = client.patch(
        "/api/v1/system/time-settings",
        json={"timezone": "Asia/Tokyo", "ntp_servers": ["time.google.com"], "ntp_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["timezone"] == "Asia/Tokyo"
    assert body["ntp_servers"] == ["time.google.com"]
    assert body["ntp_enabled"] is True

    bad = client.patch(
        "/api/v1/system/time-settings",
        json={"timezone": "Not/AZone"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_run_retention_now_admin_only(test_settings, session_factory):
    class FakeRetention:
        async def run_once(self):
            return {"audit_deleted": 1, "backups_deleted": 2, "backup_files_deleted": 2}

    runtime = ServiceRuntime.for_tests(
        test_settings,
        session_factory,
        jwt_secret=b"R" * 32,
        retention_service=FakeRetention(),
    )
    from app_v4.data.repository import Repository
    async with session_factory() as session:
        repo = Repository(session)
        admin = await repo.create_user("admin", "h", "admin")
        await session.commit()
        admin_id = admin.id
    admin_token = runtime.auth_service.issue_access_token(admin_id, "admin", "admin")

    client = TestClient(create_app(runtime))
    forbidden = client.post(
        "/api/v1/system/retention/run",
        headers={"Authorization": f"Bearer {_operator_token(runtime)}"},
    )
    assert forbidden.status_code == 403

    r = client.post(
        "/api/v1/system/retention/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {"audit_deleted": 1, "backups_deleted": 2, "backup_files_deleted": 2}


@pytest.mark.asyncio
async def test_scheduler_status_returns_jobs_and_timezone(test_settings, session_factory):
    class FakeScheduler:
        def status_snapshot(self):
            return {
                "running": True,
                "timezone": "Asia/Jakarta",
                "lock_acquired": True,
                "lock_file": "/tmp/lock",
                "jobs": [
                    {
                        "job_id": 7,
                        "next_run_time": "2026-05-23T21:53:00+07:00",
                        "trigger": "cron[hour='21', minute='53']",
                    }
                ],
            }

    runtime = ServiceRuntime.for_tests(
        test_settings,
        session_factory,
        jwt_secret=b"S" * 32,
        scheduler_service=FakeScheduler(),
    )
    client = TestClient(create_app(runtime))
    r = client.get(
        "/api/v1/system/scheduler-status",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is True
    assert body["timezone"] == "Asia/Jakarta"
    assert body["jobs"][0]["job_id"] == 7
    assert body["jobs"][0]["next_run_time"].startswith("2026-05-23T21:53")


@pytest.mark.asyncio
async def test_scheduler_status_when_unavailable(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(
        test_settings,
        session_factory,
        jwt_secret=b"S" * 32,
    )
    client = TestClient(create_app(runtime))
    r = client.get(
        "/api/v1/system/scheduler-status",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is False
    assert body["jobs"] == []

