from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app_v4.core.config import Settings
from app_v4.data.repository import Repository


class RetentionService:
    def __init__(
        self,
        settings: Settings,
        session_factory,
        runtime_settings_path: Path | None = None,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.runtime_settings_path = runtime_settings_path

    def _effective_audit_retention_days(self) -> int:
        if self.runtime_settings_path is not None and self.runtime_settings_path.exists():
            from app_v4.core.runtime_settings import load_runtime_settings
            return load_runtime_settings(self.runtime_settings_path).retention.audit_retention_days
        return self.settings.audit_retention_days

    async def trim_audit(self) -> int:
        cutoff = datetime.utcnow() - timedelta(days=self._effective_audit_retention_days())
        async with self.session_factory() as session:
            repo = Repository(session)
            deleted = await repo.delete_audit_older_than(cutoff)
            await session.commit()
            return deleted

    async def run_once(self) -> dict[str, int]:
        return {"audit_deleted": await self.trim_audit()}
