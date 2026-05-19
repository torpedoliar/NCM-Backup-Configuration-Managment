from dataclasses import dataclass

import pytest

from app_v4.data.repository import Repository
from app_v4.net.runner import BackupRunResult
from app_v4.service.backup_service import BackupService
from app_v4.service.diff_service import DiffService
from app_v4.service.events import EventHub
from app_v4.service.scheduler import SchedulerService


@dataclass
class FakeRunner:
    result: BackupRunResult

    async def execute_backup(self, protocol, host, port, username, password, enable_password=""):
        return self.result


class FakeBackupService:
    async def execute_backup(self, switch_id, backup_type="automatic", job_id=None, triggered_by_user_id=None):
        return {"success": True, "message": "ok", "backup_id": 1, "file_path": "", "size_kb": 0}


class RecordingHub(EventHub):
    def __init__(self):
        super().__init__()
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_backup_service_broadcasts_lifecycle_events(test_settings, session_factory, crypto_service):
    hub = RecordingHub()
    service = BackupService(
        settings=test_settings,
        session_factory=session_factory,
        crypto_service=crypto_service,
        runner=FakeRunner(BackupRunResult(True, "hostname sw01", "Backup completed successfully")),
        diff_service=DiffService(test_settings),
        event_hub=hub,
    )
    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("admin", "secret", "")
        cred = await repo.create_credential("cred", blob)
        switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        switch_id = switch.id

    await service.execute_backup(switch_id=switch_id, backup_type="manual", triggered_by_user_id=None)

    assert [event.type for event in hub.events] == ["backup_started", "backup_completed"]
    assert hub.events[0].payload["switch_id"] == switch_id
    assert hub.events[1].payload["backup_id"] == 1


@pytest.mark.asyncio
async def test_scheduler_broadcasts_job_triggered(test_settings, session_factory):
    hub = RecordingHub()
    scheduler = SchedulerService(test_settings, session_factory, FakeBackupService(), event_hub=hub)
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        job = await repo.create_job(switch.id, 60, True, 8, 30)
        await session.commit()
        job_id = job.id
        switch_id = switch.id

    await scheduler.execute_scheduled_backup(job_id, switch_id)

    assert [event.type for event in hub.events] == ["job_triggered"]
    assert hub.events[0].payload == {"job_id": job_id, "switch_id": switch_id}
