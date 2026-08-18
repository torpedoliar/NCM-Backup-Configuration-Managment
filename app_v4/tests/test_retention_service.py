from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app_v4.data.models import AuditLog
from app_v4.data.repository import Repository
from app_v4.service.retention_service import RetentionService


@pytest.mark.asyncio
async def test_retention_removes_old_audit_rows(test_settings, session_factory):
    async with session_factory() as session:
        session.add(AuditLog(user_id=None, action="old", ts=datetime.utcnow() - timedelta(days=100)))
        session.add(AuditLog(user_id=None, action="new", ts=datetime.utcnow()))
        await session.commit()

    service = RetentionService(test_settings, session_factory)
    deleted = await service.trim_audit()

    assert deleted == 1
    async with session_factory() as session:
        rows = await Repository(session).list_audit(limit=10)
    assert [row.action for row in rows] == ["new"]


@pytest.mark.asyncio
async def test_retention_service_uses_runtime_settings_for_audit_days(tmp_path, session_factory):
    from app_v4.core.runtime_settings import RetentionSettings, RuntimeSettings, save_runtime_settings
    from app_v4.service.retention_service import RetentionService
    from app_v4.core.config import Settings

    rs_file = tmp_path / "data" / "runtime_settings.json"
    save_runtime_settings(rs_file, RuntimeSettings(retention=RetentionSettings(audit_retention_days=7)))
    settings = Settings(base_dir=tmp_path)
    service = RetentionService(settings, session_factory, runtime_settings_path=rs_file)
    assert service._effective_audit_retention_days() == 7


@pytest.mark.asyncio
async def test_retention_prunes_old_backup_rows_and_files(tmp_path: Path, test_settings, session_factory):
    from app_v4.core.runtime_settings import (
        RetentionSettings,
        RuntimeSettings,
        save_runtime_settings,
    )

    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    rs_file = tmp_path / "runtime_settings.json"
    save_runtime_settings(
        rs_file,
        RuntimeSettings(
            retention=RetentionSettings(
                backup_min_keep=1, backup_retention_days=7, audit_retention_days=30
            )
        ),
    )

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        recent_path = backups_dir / "recent.txt"
        old_path = backups_dir / "old.txt"
        very_old_path = backups_dir / "very-old.txt"
        recent_path.write_text("recent")
        old_path.write_text("old")
        very_old_path.write_text("very-old")
        recent = await repo.create_backup(switch.id, str(recent_path), "h1", 6, True, "ok")
        old = await repo.create_backup(switch.id, str(old_path), "h2", 3, True, "ok")
        very_old = await repo.create_backup(switch.id, str(very_old_path), "h3", 8, True, "ok")
        # backdate the older ones beyond the retention window
        old.taken_at = datetime.utcnow() - timedelta(days=30)
        very_old.taken_at = datetime.utcnow() - timedelta(days=120)
        await session.commit()
        recent_id = recent.id
        old_id = old.id
        very_old_id = very_old.id

    service = RetentionService(test_settings, session_factory, runtime_settings_path=rs_file)
    summary = await service.trim_backups()

    assert summary["backups_deleted"] == 2
    assert summary["backup_files_deleted"] == 2
    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_backup(recent_id) is not None
        assert await repo.get_backup(old_id) is None
        assert await repo.get_backup(very_old_id) is None
    assert recent_path.exists()
    assert not old_path.exists()
    assert not very_old_path.exists()


@pytest.mark.asyncio
async def test_retention_keeps_min_keep_even_if_all_old(tmp_path: Path, test_settings, session_factory):
    from app_v4.core.runtime_settings import (
        RetentionSettings,
        RuntimeSettings,
        save_runtime_settings,
    )

    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    rs_file = tmp_path / "runtime_settings.json"
    save_runtime_settings(
        rs_file,
        RuntimeSettings(
            retention=RetentionSettings(
                backup_min_keep=2, backup_retention_days=1, audit_retention_days=30
            )
        ),
    )

    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("cred", b"x")
        switch = await repo.create_switch("sw", "10.0.0.1", "ssh", 22, cred.id)
        paths = []
        ids = []
        for i in range(4):
            p = backups_dir / f"b{i}.txt"
            p.write_text(str(i))
            paths.append(p)
            row = await repo.create_backup(switch.id, str(p), f"h{i}", 1, True, "ok")
            row.taken_at = datetime.utcnow() - timedelta(days=20 - i)  # all older than 1 day
            ids.append(row.id)
        await session.commit()

    service = RetentionService(test_settings, session_factory, runtime_settings_path=rs_file)
    await service.trim_backups()

    async with session_factory() as session:
        repo = Repository(session)
        survivors = [b for b in await repo.list_backups() if b.switch_id is not None]
    assert len(survivors) == 2
