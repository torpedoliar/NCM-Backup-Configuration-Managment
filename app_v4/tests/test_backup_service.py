from dataclasses import dataclass
from pathlib import Path

import pytest

from app_v4.data.repository import Repository
from app_v4.net.runner import BackupRunResult
from app_v4.service.backup_service import BackupService
from app_v4.service.diff_service import DiffService


@dataclass
class FakeRunner:
    result: BackupRunResult

    async def execute_backup(self, protocol, host, port, username, password, enable_password=""):
        return self.result


@pytest.mark.asyncio
async def test_backup_service_creates_success_record_and_file(test_settings, session_factory, crypto_service):
    service = BackupService(
        settings=test_settings,
        session_factory=session_factory,
        crypto_service=crypto_service,
        runner=FakeRunner(BackupRunResult(True, "config text", "Backup completed successfully")),
        diff_service=DiffService(test_settings),
    )
    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("admin", "secret", "enable")
        cred = await repo.create_credential("cred", blob)
        switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        switch_id = switch.id

    result = await service.execute_backup(switch_id=switch_id, backup_type="manual", triggered_by_user_id=None)

    assert result["success"] is True
    assert result["backup_id"]
    assert Path(result["file_path"]).exists()
    assert Path(result["file_path"]).read_text(encoding="utf-8") == "config text"


@pytest.mark.asyncio
async def test_backup_service_creates_failed_record(test_settings, session_factory, crypto_service):
    service = BackupService(
        settings=test_settings,
        session_factory=session_factory,
        crypto_service=crypto_service,
        runner=FakeRunner(BackupRunResult(False, "", "boom")),
        diff_service=DiffService(test_settings),
    )
    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("admin", "secret", "")
        cred = await repo.create_credential("cred", blob)
        switch = await repo.create_switch("sw01", "10.0.0.1", "ssh", 22, cred.id)
        await session.commit()
        switch_id = switch.id

    result = await service.execute_backup(switch_id=switch_id, backup_type="manual", triggered_by_user_id=None)

    assert result["success"] is False
    assert result["message"] == "boom"
    async with session_factory() as session:
        repo = Repository(session)
        backup = await repo.get_backup(result["backup_id"])
    assert backup.success is False
