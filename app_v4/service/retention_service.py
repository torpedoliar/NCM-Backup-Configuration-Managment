from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app_v4.core.config import Settings
from app_v4.data.models import Backup, Switch
from app_v4.data.repository import Repository

logger = logging.getLogger(__name__)


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

    def _effective_retention_settings(self):
        if self.runtime_settings_path is not None and self.runtime_settings_path.exists():
            from app_v4.core.runtime_settings import load_runtime_settings
            return load_runtime_settings(self.runtime_settings_path).retention
        from app_v4.core.runtime_settings import RetentionSettings
        return RetentionSettings(
            backup_min_keep=self.settings.backup_min_keep,
            backup_retention_days=self.settings.backup_retention_days,
            audit_retention_days=self.settings.audit_retention_days,
            retention_hour=self.settings.retention_hour,
            retention_minute=self.settings.retention_minute,
        )

    def _effective_audit_retention_days(self) -> int:
        return self._effective_retention_settings().audit_retention_days

    async def trim_audit(self) -> int:
        cutoff = datetime.utcnow() - timedelta(days=self._effective_audit_retention_days())
        async with self.session_factory() as session:
            repo = Repository(session)
            deleted = await repo.delete_audit_older_than(cutoff)
            await session.commit()
            return deleted

    async def trim_backups(self) -> dict[str, int]:
        cfg = self._effective_retention_settings()
        cutoff = datetime.utcnow() - timedelta(days=cfg.backup_retention_days)
        deleted_rows = 0
        deleted_files = 0
        async with self.session_factory() as session:
            switch_ids = (await session.execute(select(Switch.id))).scalars().all()
            for switch_id in switch_ids:
                rows = (
                    await session.execute(
                        select(Backup)
                        .where(Backup.switch_id == switch_id)
                        .order_by(Backup.taken_at.desc())
                    )
                ).scalars().all()
                if not rows:
                    continue
                # Always keep the N most recent regardless of age.
                keep = rows[: max(1, cfg.backup_min_keep)]
                candidates = rows[max(1, cfg.backup_min_keep):]
                for backup in candidates:
                    if backup in keep:
                        continue
                    if backup.taken_at >= cutoff:
                        continue
                    file_path = backup.file_path
                    await session.delete(backup)
                    deleted_rows += 1
                    if file_path:
                        try:
                            p = Path(file_path)
                            if p.exists():
                                p.unlink()
                                deleted_files += 1
                        except OSError as exc:
                            logger.warning("retention unlink failed: %s (%s)", exc, file_path)
            await session.commit()
        return {"backups_deleted": deleted_rows, "backup_files_deleted": deleted_files}

    async def run_once(self) -> dict[str, int]:
        result = {"audit_deleted": await self.trim_audit()}
        result.update(await self.trim_backups())
        return result
