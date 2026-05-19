import pytest

from app_v4.data.repository import Repository
from app_v4.service.scheduler import SchedulerService


class FakeBackupService:
    def __init__(self):
        self.calls = []

    async def execute_backup(self, switch_id, backup_type="automatic", job_id=None, triggered_by_user_id=None):
        self.calls.append((switch_id, backup_type, job_id, triggered_by_user_id))
        return {"success": True, "message": "ok", "backup_id": 1, "file_path": "", "size_kb": 0}


@pytest.mark.asyncio
async def test_scheduler_sync_registers_enabled_jobs(test_settings, session_factory):
    backup_service = FakeBackupService()
    scheduler = SchedulerService(test_settings, session_factory, backup_service)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        job = await repo.create_job(switch.id, 60, True, 8, 30)
        await session.commit()
        job_id = job.id

    await scheduler.sync_once()

    assert job_id in scheduler.job_map
    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_execute_job_runs_backup_and_updates_last_run(test_settings, session_factory):
    backup_service = FakeBackupService()
    scheduler = SchedulerService(test_settings, session_factory, backup_service)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        job = await repo.create_job(switch.id, 60, True, 8, 30)
        await session.commit()
        job_id = job.id
        switch_id = switch.id

    await scheduler.execute_scheduled_backup(job_id, switch_id)

    assert backup_service.calls == [(switch_id, "automatic", job_id, None)]
    async with session_factory() as session:
        repo = Repository(session)
        loaded = await repo.get_job(job_id)
    assert loaded.last_ran_at is not None
