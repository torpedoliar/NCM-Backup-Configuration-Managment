from __future__ import annotations

from datetime import datetime, timedelta

from app_v4.core.config import Settings
from app_v4.data.repository import Repository


class RetentionService:
    def __init__(self, settings: Settings, session_factory):
        self.settings = settings
        self.session_factory = session_factory

    async def trim_audit(self) -> int:
        cutoff = datetime.utcnow() - timedelta(days=self.settings.audit_retention_days)
        async with self.session_factory() as session:
            repo = Repository(session)
            deleted = await repo.delete_audit_older_than(cutoff)
            await session.commit()
            return deleted

    async def run_once(self) -> dict[str, int]:
        return {"audit_deleted": await self.trim_audit()}
