from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService
from app_v4.core.paths import resolve_paths
from app_v4.data.repository import Repository
from app_v4.net.runner import BackupRunner
from app_v4.service.diff_service import DiffService
from app_v4.service.events import EventHub, publish


class BackupService:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        crypto_service: CryptoService,
        runner: BackupRunner | None = None,
        diff_service: DiffService | None = None,
        event_hub: EventHub | None = None,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.crypto_service = crypto_service
        self.runner = runner or BackupRunner(settings)
        self.diff_service = diff_service or DiffService(settings)
        self.event_hub = event_hub

    async def execute_backup(
        self,
        switch_id: int,
        backup_type: str = "manual",
        job_id: int | None = None,
        triggered_by_user_id: int | None = None,
    ) -> dict:
        async with self.session_factory() as session:
            repo = Repository(session)
            switch = await repo.get_switch(switch_id)
            if switch is None:
                raise ValueError(f"Switch ID {switch_id} not found")
            switch_name = switch.name
            protocol = switch.protocol
            host = switch.ip
            port = switch.port
            enc_blob = switch.credential.enc_blob

        await publish(self.event_hub, "backup_started", {"switch_id": switch_id, "switch_name": switch_name, "backup_type": backup_type})
        credentials = self.crypto_service.decrypt_credential(enc_blob)
        run_result = await self.runner.execute_backup(
            protocol=protocol,
            host=host,
            port=port,
            username=credentials["username"],
            password=credentials["password"],
            enable_password=credentials.get("enable_password", ""),
        )

        if not run_result.success:
            result = await self._record_failed_backup(
                switch_id=switch_id,
                message=run_result.message,
                backup_type=backup_type,
                job_id=job_id,
                triggered_by_user_id=triggered_by_user_id,
                error_code=run_result.error_code,
            )
            await publish(
                self.event_hub,
                "backup_failed",
                {"switch_id": switch_id, "switch_name": switch_name, "backup_id": result["backup_id"], "message": run_result.message},
            )
            return result

        content_hash = hashlib.sha256(run_result.config_text.encode("utf-8")).hexdigest()
        changed = False
        diff_stats = None
        previous_text = None
        async with self.session_factory() as session:
            repo = Repository(session)
            previous = await repo.get_latest_backup(switch_id)
            if previous is not None:
                changed = previous.content_hash != content_hash
                if previous.file_path:
                    previous_path = Path(previous.file_path)
                    if previous_path.exists():
                        previous_text = previous_path.read_text(encoding="utf-8")

        file_path = self._save_config_file(switch_name, run_result.config_text, changed)
        if changed and previous_text is not None:
            diff_text = self.diff_service.unified_diff(previous_text, run_result.config_text, "Previous", "Current")
            diff_stats = self.diff_service.get_diff_stats(previous_text, run_result.config_text)
            self.diff_service.export_diff(diff_text, Path(str(file_path).rsplit(".txt", 1)[0] + ".diff"))

        if changed:
            if diff_stats:
                message = f"Perubahan konfigurasi terdeteksi: +{diff_stats['added_lines']}/-{diff_stats['removed_lines']}/~{diff_stats['changed_lines']} baris"
            else:
                message = "Perubahan konfigurasi terdeteksi"
        else:
            message = "Tidak ada perubahan konfigurasi"

        async with self.session_factory() as session:
            repo = Repository(session)
            backup = await repo.create_backup(
                switch_id=switch_id,
                file_path=str(file_path),
                content_hash=content_hash,
                size_bytes=len(run_result.config_text.encode("utf-8")),
                success=True,
                message=message,
                backup_type=backup_type,
                job_id=job_id,
                triggered_by_user_id=triggered_by_user_id,
            )
            await session.commit()
            backup_id = backup.id

        await publish(self.event_hub, "backup_completed", {"switch_id": switch_id, "switch_name": switch_name, "backup_id": backup_id})
        return {
            "success": True,
            "message": message,
            "file_path": str(file_path),
            "size_kb": len(run_result.config_text.encode("utf-8")) / 1024,
            "backup_id": backup_id,
        }

    async def _record_failed_backup(
        self,
        switch_id: int,
        message: str,
        backup_type: str,
        job_id: int | None,
        triggered_by_user_id: int | None,
        error_code: str | None = None,
    ) -> dict:
        async with self.session_factory() as session:
            repo = Repository(session)
            backup = await repo.create_backup(
                switch_id=switch_id,
                file_path="",
                content_hash="",
                size_bytes=0,
                success=False,
                message=message,
                backup_type=backup_type,
                job_id=job_id,
                triggered_by_user_id=triggered_by_user_id,
            )
            await session.commit()
            backup_id = backup.id
        return {"success": False, "message": message, "file_path": "", "size_kb": 0, "backup_id": backup_id, "error_code": error_code}

    def _save_config_file(self, switch_name: str, config_text: str, changed: bool) -> Path:
        paths = resolve_paths(self.settings)
        now = datetime.now()
        backup_dir = paths.backups_dir / switch_name / now.strftime("%Y-%m-%d")
        backup_dir.mkdir(parents=True, exist_ok=True)
        suffix = " - update config" if changed else ""
        file_path = backup_dir / f"{now.strftime('%H%M%S')}_running-config{suffix}.txt"
        file_path.write_text(config_text, encoding="utf-8")
        return file_path

    def get_backup_content(self, file_path: str) -> str:
        return Path(file_path).read_text(encoding="utf-8")
