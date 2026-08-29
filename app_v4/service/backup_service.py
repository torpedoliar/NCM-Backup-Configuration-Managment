from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.core.crypto_service import CryptoService
from app_v4.core.paths import resolve_paths
from app_v4.data.repository import Repository
from app_v4.net.runner import BackupRunner
from app_v4.service.diff_service import DiffService
from app_v4.service.events import EventHub, publish


class SwitchInactiveError(ValueError):
    """Raised by execute_backup when the target switch is inactive."""


class BackupService:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        crypto_service: CryptoService,
        runner: BackupRunner | None = None,
        diff_service: DiffService | None = None,
        event_hub: EventHub | None = None,
        review_service=None,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.crypto_service = crypto_service
        self.runner = runner or BackupRunner(settings)
        self.diff_service = diff_service or DiffService(settings)
        self.event_hub = event_hub
        self.review_service = review_service
        # Manual, scheduled, and catch-up triggers can target the same switch.
        # Serialize only that switch; different switches can still run in parallel.
        self._switch_locks: dict[int, asyncio.Lock] = {}

    async def execute_backup(
        self,
        switch_id: int,
        backup_type: str = "manual",
        job_id: int | None = None,
        triggered_by_user_id: int | None = None,
    ) -> dict:
        lock = self._switch_locks.setdefault(switch_id, asyncio.Lock())
        async with lock:
            try:
                return await self._execute_backup(
                    switch_id=switch_id,
                    backup_type=backup_type,
                    job_id=job_id,
                    triggered_by_user_id=triggered_by_user_id,
                )
            except Exception as exc:
                # Missing/inactive switches are API validation errors and must
                # retain their existing HTTP behavior. Other failures belong
                # in the backup history so a failed device is observable.
                async with self.session_factory() as session:
                    repo = Repository(session)
                    switch = await repo.get_switch(switch_id)
                if switch is None or not switch.is_active:
                    raise

                message = f"Backup failed: {exc}" or "Backup failed"
                result = await self._record_failed_backup(
                    switch_id=switch_id,
                    message=message,
                    backup_type=backup_type,
                    job_id=job_id,
                    triggered_by_user_id=triggered_by_user_id,
                    error_code=self._categorize_exception(exc),
                )
                await publish(
                    self.event_hub,
                    "backup_failed",
                    {
                        "switch_id": switch_id,
                        "switch_name": switch.name,
                        "backup_id": result["backup_id"],
                        "message": message,
                    },
                )
                return result

    async def _execute_backup(
        self,
        switch_id: int,
        backup_type: str,
        job_id: int | None,
        triggered_by_user_id: int | None,
    ) -> dict:
        async with self.session_factory() as session:
            repo = Repository(session)
            switch = await repo.get_switch(switch_id)
            if switch is None:
                raise ValueError(f"Switch ID {switch_id} not found")
            if not switch.is_active:
                raise SwitchInactiveError(f"Switch {switch_id} is inactive")
            switch_name = switch.name
            protocol = switch.protocol
            host = switch.ip
            port = switch.port
            enc_blob = switch.credential.enc_blob

        await publish(self.event_hub, "backup_started", {"switch_id": switch_id, "switch_name": switch_name, "backup_type": backup_type})
        try:
            credentials = self.crypto_service.decrypt_credential(enc_blob)
        except ValueError as exc:
            raise ValueError(
                f"Credential for switch {switch_name!r} cannot be decrypted "
                "(master key mismatch or corrupted blob); recreate the credential"
            ) from exc
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

        if self.review_service is not None:
            review_id = await self._run_drift_review(
                switch,
                backup_id,
                content_hash,
                run_result.config_text,
            )
            if review_id is not None:
                await publish(
                    self.event_hub,
                    "config_drift",
                    {
                        "switch_id": switch_id,
                        "switch_name": switch_name,
                        "backup_id": backup_id,
                        "review_id": review_id,
                    },
                )

        await publish(self.event_hub, "backup_completed", {"switch_id": switch_id, "switch_name": switch_name, "backup_id": backup_id})
        return {
            "success": True,
            "message": message,
            "file_path": str(file_path),
            "size_kb": len(run_result.config_text.encode("utf-8")) / 1024,
            "backup_id": backup_id,
        }

    async def _run_drift_review(
        self,
        switch,
        backup_id: int,
        content_hash: str,
        content_text: str,
    ) -> int | None:
        """Compare the new backup against the applicable baseline and log a review.

        Never raises: review failures are logged by ReviewService and the backup
        outcome is unaffected.
        """
        try:
            async with self.session_factory() as session:
                repo = Repository(session)
                baseline = await repo.get_baseline_for_switch(switch)
                baseline_text = None
                baseline_id = baseline.id if baseline is not None else None
                if baseline is not None and baseline.backup_id is not None:
                    source = await repo.get_backup(baseline.backup_id)
                    if source is not None and source.file_path:
                        path = Path(source.file_path)
                        if path.exists():
                            baseline_text = path.read_text(encoding="utf-8")
            outcome = await self.review_service.on_backup_complete(
                switch=switch,
                backup_id=backup_id,
                content_text=content_text,
                baseline_text=baseline_text,
                baseline_id=baseline_id,
            )
            return outcome.review_id if outcome.drifted else None
        except Exception:  # noqa: BLE001 - review must never break backups
            import logging
            logging.getLogger(__name__).exception(
                "drift review failed after backup for switch %s", switch.id
            )
            return None

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

    def _categorize_exception(self, exc: Exception) -> str:
        text = str(exc).lower()
        if isinstance(exc, TimeoutError) or "timeout" in text or "timed out" in text:
            return "CONNECTION_TIMEOUT"
        if isinstance(exc, PermissionError) or "auth" in text or "password" in text:
            return "AUTHENTICATION_ERROR"
        if "prompt" in text or "incomplete" in text:
            return "INCOMPLETE_OUTPUT"
        return "UNKNOWN"

    def _save_config_file(self, switch_name: str, config_text: str, changed: bool) -> Path:
        paths = resolve_paths(self.settings)
        now = datetime.now()
        backup_dir = paths.backups_dir / switch_name / now.strftime("%Y-%m-%d")
        backup_dir.mkdir(parents=True, exist_ok=True)
        suffix = " - update config" if changed else ""
        stamp = now.strftime("%H%M%S_%f")
        file_path = backup_dir / f"{stamp}_running-config{suffix}.txt"
        if file_path.exists():
            file_path = backup_dir / f"{stamp}_{uuid4().hex[:8]}_running-config{suffix}.txt"
        file_path.write_text(config_text, encoding="utf-8")
        return file_path

    def get_backup_content(self, file_path: str) -> str:
        return Path(file_path).read_text(encoding="utf-8")
