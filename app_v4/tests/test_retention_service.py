from datetime import datetime, timedelta

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
