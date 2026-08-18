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


@pytest.mark.asyncio
async def test_scheduler_skips_jobs_for_inactive_switches(test_settings, session_factory):
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

    await scheduler.sync_once()
    assert job_id in scheduler.job_map

    async with session_factory() as session:
        repo = Repository(session)
        await repo.deactivate_switch(switch_id)
        await session.commit()

    await scheduler.sync_once()
    assert job_id not in scheduler.job_map

    await scheduler.stop()


def test_build_trigger_weekly_uses_day_of_week(test_settings, session_factory):
    backup_service = FakeBackupService()
    scheduler = SchedulerService(test_settings, session_factory, backup_service)
    trigger = scheduler._build_trigger(
        interval_minutes=10080,
        schedule_hour=8,
        schedule_minute=30,
        day_of_week="fri",
        day_of_month=None,
    )
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields["day_of_week"] == "fri"
    assert fields["hour"] == "8"
    assert fields["minute"] == "30"


def test_build_trigger_monthly_uses_day_of_month(test_settings, session_factory):
    backup_service = FakeBackupService()
    scheduler = SchedulerService(test_settings, session_factory, backup_service)
    trigger = scheduler._build_trigger(
        interval_minutes=43200,
        schedule_hour=2,
        schedule_minute=0,
        day_of_week=None,
        day_of_month=15,
    )
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields["day"] == "15"
    assert fields["hour"] == "2"


def test_scheduler_default_timezone_is_asia_jakarta(test_settings, session_factory):
    backup_service = FakeBackupService()
    scheduler = SchedulerService(test_settings, session_factory, backup_service)
    assert str(scheduler.timezone) == "Asia/Jakarta"
    daily = scheduler._build_trigger(
        interval_minutes=1440,
        schedule_hour=12,
        schedule_minute=50,
        day_of_week=None,
        day_of_month=None,
    )
    assert str(daily.timezone) == "Asia/Jakarta"


def test_scheduler_uses_runtime_timezone_setting(tmp_path, session_factory):
    from app_v4.core.config import Settings
    from app_v4.core.runtime_settings import RuntimeSettings, TimeSettings, save_runtime_settings

    settings = Settings(base_dir=tmp_path)
    rs_file = tmp_path / "data" / "runtime_settings.json"
    save_runtime_settings(rs_file, RuntimeSettings(time=TimeSettings(timezone="Asia/Tokyo")))

    backup_service = FakeBackupService()
    scheduler = SchedulerService(settings, session_factory, backup_service)
    assert str(scheduler.timezone) == "Asia/Tokyo"


@pytest.mark.asyncio
async def test_scheduler_catch_up_runs_enabled_jobs_once_on_start(test_settings, session_factory):
    """Match legacy pattern: when the backend starts, run every enabled job
    once so missed schedules during downtime still produce a backup."""
    backup_service = FakeBackupService()
    scheduler = SchedulerService(test_settings, session_factory, backup_service)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        sw_a = await repo.create_switch("sw-a", "10.0.0.1", "ssh", 22, cred.id)
        sw_b = await repo.create_switch("sw-b", "10.0.0.2", "ssh", 22, cred.id)
        sw_c = await repo.create_switch("sw-c", "10.0.0.3", "ssh", 22, cred.id)
        await repo.create_job(sw_a.id, 1440, enabled=True)
        await repo.create_job(sw_b.id, 1440, enabled=False)  # disabled, must skip
        await repo.create_job(sw_c.id, 1440, enabled=True)
        await session.commit()
        sw_a_id, sw_c_id = sw_a.id, sw_c.id

    summary = await scheduler.catch_up_missed_schedules()

    assert summary["started"] == 2
    assert summary["skipped_disabled"] == 1
    triggered_switch_ids = sorted(call[0] for call in backup_service.calls)
    assert triggered_switch_ids == sorted([sw_a_id, sw_c_id])


@pytest.mark.asyncio
async def test_scheduler_catch_up_skips_inactive_switches(test_settings, session_factory):
    backup_service = FakeBackupService()
    scheduler = SchedulerService(test_settings, session_factory, backup_service)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        sw = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        await repo.create_job(sw.id, 1440, enabled=True)
        await repo.deactivate_switch(sw.id)
        await session.commit()

    summary = await scheduler.catch_up_missed_schedules()

    assert summary["started"] == 0
    assert summary["skipped_inactive_switch"] == 1
    assert backup_service.calls == []
