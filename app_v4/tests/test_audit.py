import pytest

from app_v4.data.repository import Repository
from app_v4.service.audit import AuditWriter


@pytest.mark.asyncio
async def test_audit_writer_records_event(session_factory):
    writer = AuditWriter(session_factory)

    await writer.record(
        user_id=None,
        action="auth.login",
        target_type="user",
        target_id="42",
        ip="127.0.0.1",
        detail={"username": "admin"},
    )

    async with session_factory() as session:
        repo = Repository(session)
        rows = await repo.list_audit(limit=10)

    assert len(rows) == 1
    assert rows[0].action == "auth.login"
    assert rows[0].target_id == "42"
    assert rows[0].detail_json is not None
    assert "admin" in rows[0].detail_json


@pytest.mark.asyncio
async def test_audit_writer_handles_no_detail(session_factory):
    writer = AuditWriter(session_factory)

    await writer.record(user_id=None, action="auth.logout")

    async with session_factory() as session:
        repo = Repository(session)
        rows = await repo.list_audit(limit=10)

    assert rows[0].detail_json is None
