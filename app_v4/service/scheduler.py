from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.core.paths import resolve_paths
from app_v4.core.runtime_settings import load_runtime_settings
from app_v4.data.repository import Repository
from app_v4.service.backup_service import BackupService
from app_v4.service.events import EventHub, publish
from app_v4.service.retention_service import RetentionService


def _resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                return exit_code.value == 259  # STILL_ACTIVE
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return True  # be conservative on failure
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


class SchedulerService:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        backup_service: BackupService,
        event_hub: EventHub | None = None,
        retention_service: RetentionService | None = None,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.backup_service = backup_service
        self.event_hub = event_hub
        self.retention_service = retention_service
        self._lock_file = resolve_paths(settings).scheduler_lock_file
        self._runtime_settings_path = resolve_paths(settings).data_dir / "runtime_settings.json"
        self.timezone = _resolve_timezone(self._effective_timezone_name())
        self.scheduler = AsyncIOScheduler(
            timezone=self.timezone,
            job_defaults={"coalesce": False, "max_instances": 3},
        )
        self.job_map: dict[int, str] = {}
        self.job_interval_map: dict[int, int] = {}
        self.job_time_map: dict[int, tuple[int, int]] = {}
        self._sync_task: asyncio.Task | None = None
        self._lock_acquired = False

    def _effective_timezone_name(self) -> str:
        try:
            return load_runtime_settings(self._runtime_settings_path).time.timezone
        except Exception:
            return "Asia/Jakarta"

    async def start(self) -> bool:
        if not self._acquire_lock():
            return False
        self.scheduler.start()
        if self.retention_service is not None:
            self.scheduler.add_job(
                self.retention_service.run_once,
                CronTrigger(
                    hour=self.settings.retention_hour,
                    minute=self.settings.retention_minute,
                    timezone=self.timezone,
                ),
                id="retention-nightly",
                replace_existing=True,
            )
        await self.sync_once()
        # Match legacy: run enabled jobs once on startup so missed schedules
        # while the host/backend was offline still get a backup. Failures
        # inside catch-up don't block scheduler readiness.
        try:
            await self.catch_up_missed_schedules()
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "catch_up_missed_schedules failed during start", exc_info=True
            )
        self._sync_task = asyncio.create_task(self._sync_loop())
        return True

    async def stop(self) -> None:
        if self._sync_task is not None:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self._release_lock()

    async def sync_once(self) -> None:
        async with self.session_factory() as session:
            repo = Repository(session)
            jobs = await repo.list_jobs()
            switches = await repo.list_switches(include_inactive=True)
        active_switch_ids = {sw.id for sw in switches if sw.is_active}
        runnable_ids = {job.id for job in jobs if job.enabled and job.switch_id in active_switch_ids}
        for job_id in list(self.job_map):
            if job_id not in runnable_ids:
                self.remove_job(job_id)
        for job in jobs:
            if not job.enabled or job.switch_id not in active_switch_ids:
                continue
            time_pair = (job.schedule_hour, job.schedule_minute)
            if job.id not in self.job_map:
                self.add_job(
                    job.id,
                    job.switch_id,
                    job.interval_minutes,
                    job.schedule_hour,
                    job.schedule_minute,
                    job.day_of_week,
                    job.day_of_month,
                )
            elif self.job_interval_map.get(job.id) != job.interval_minutes or self.job_time_map.get(job.id) != time_pair:
                self.remove_job(job.id)
                self.add_job(
                    job.id,
                    job.switch_id,
                    job.interval_minutes,
                    job.schedule_hour,
                    job.schedule_minute,
                    job.day_of_week,
                    job.day_of_month,
                )

    def add_job(
        self,
        job_id: int,
        switch_id: int,
        interval_minutes: int,
        schedule_hour: int,
        schedule_minute: int,
        day_of_week: str | None = None,
        day_of_month: int | None = None,
    ) -> None:
        aps_id = f"backup_job_{job_id}"
        self.scheduler.add_job(
            self.execute_scheduled_backup,
            trigger=self._build_trigger(
                interval_minutes,
                schedule_hour,
                schedule_minute,
                day_of_week,
                day_of_month,
            ),
            id=aps_id,
            args=[job_id, switch_id],
            replace_existing=True,
            name=f"Backup Job {job_id}",
        )
        self.job_map[job_id] = aps_id
        self.job_interval_map[job_id] = interval_minutes
        self.job_time_map[job_id] = (schedule_hour, schedule_minute)

    def remove_job(self, job_id: int) -> None:
        aps_id = self.job_map.pop(job_id, None)
        self.job_interval_map.pop(job_id, None)
        self.job_time_map.pop(job_id, None)
        if aps_id and self.scheduler.get_job(aps_id):
            self.scheduler.remove_job(aps_id)

    def reschedule_retention(self, hour: int, minute: int) -> None:
        if self.scheduler.get_job("retention-nightly"):
            self.scheduler.reschedule_job(
                "retention-nightly",
                trigger=CronTrigger(hour=hour, minute=minute, timezone=self.timezone),
            )

    def reload_timezone(self) -> None:
        new_tz = _resolve_timezone(self._effective_timezone_name())
        if new_tz.key == self.timezone.key:
            return
        self.timezone = new_tz
        self.scheduler.configure(timezone=new_tz)
        if self.scheduler.get_job("retention-nightly"):
            self.scheduler.reschedule_job(
                "retention-nightly",
                trigger=CronTrigger(
                    hour=self.settings.retention_hour,
                    minute=self.settings.retention_minute,
                    timezone=new_tz,
                ),
            )
        for job_id in list(self.job_map):
            self.remove_job(job_id)
        # Trigger sync_loop to reattach jobs with the new tz on next iteration.

    def next_run_for(self, job_id: int) -> datetime | None:
        aps_id = self.job_map.get(job_id)
        if aps_id is None:
            return None
        aps_job = self.scheduler.get_job(aps_id)
        if aps_job is None:
            return None
        return aps_job.next_run_time

    def status_snapshot(self) -> dict:
        snapshot = {
            "running": bool(self.scheduler.running),
            "timezone": str(self.timezone.key),
            "lock_acquired": self._lock_acquired,
            "lock_file": str(self._lock_file),
            "jobs": [],
        }
        for job_id, aps_id in self.job_map.items():
            aps_job = self.scheduler.get_job(aps_id)
            snapshot["jobs"].append(
                {
                    "job_id": job_id,
                    "next_run_time": aps_job.next_run_time.isoformat() if aps_job and aps_job.next_run_time else None,
                    "trigger": str(aps_job.trigger) if aps_job else None,
                }
            )
        return snapshot

    async def execute_scheduled_backup(self, job_id: int, switch_id: int) -> None:
        started_at = datetime.utcnow()
        await publish(self.event_hub, "job_triggered", {"job_id": job_id, "switch_id": switch_id})
        await self.backup_service.execute_backup(
            switch_id=switch_id,
            backup_type="automatic",
            job_id=job_id,
            triggered_by_user_id=None,
        )
        async with self.session_factory() as session:
            repo = Repository(session)
            await repo.update_job(job_id, last_ran_at=started_at)
            await session.commit()

    async def catch_up_missed_schedules(self) -> dict[str, int]:
        """Run every enabled job once on startup, mirroring legacy v3 behavior.

        Why: when the host was off (or the backend was down) the scheduled
        firing time passes silently. APScheduler's interval/cron triggers do
        not back-date — they only fire from the next match forward. Running
        each enabled job once at startup recovers a backup that would
        otherwise have been missed and matches what the legacy app did.

        Skipped jobs (disabled or pointing at a deactivated switch) are
        counted in the return value so callers / tests can verify the
        decision path.
        """
        started = 0
        skipped_disabled = 0
        skipped_inactive_switch = 0
        async with self.session_factory() as session:
            repo = Repository(session)
            jobs = await repo.list_jobs()
            switches = await repo.list_switches(include_inactive=True)
        active_switch_ids = {sw.id for sw in switches if sw.is_active}

        for job in jobs:
            if not job.enabled:
                skipped_disabled += 1
                continue
            if job.switch_id not in active_switch_ids:
                skipped_inactive_switch += 1
                continue
            try:
                await self.execute_scheduled_backup(job.id, job.switch_id)
                started += 1
            except Exception:  # noqa: BLE001
                # Catch-up is best-effort; one failing device must not stop
                # the rest. The regular trigger fires on its own next match.
                import logging
                logging.getLogger(__name__).exception(
                    "catch-up backup for job %s failed", job.id
                )
        return {
            "started": started,
            "skipped_disabled": skipped_disabled,
            "skipped_inactive_switch": skipped_inactive_switch,
        }

    def _build_trigger(
        self,
        interval_minutes: int,
        schedule_hour: int,
        schedule_minute: int,
        day_of_week: str | None,
        day_of_month: int | None,
    ):
        if interval_minutes == 1440:
            return CronTrigger(hour=schedule_hour, minute=schedule_minute, timezone=self.timezone)
        if interval_minutes == 10080:
            return CronTrigger(
                day_of_week=day_of_week or "mon",
                hour=schedule_hour,
                minute=schedule_minute,
                timezone=self.timezone,
            )
        if interval_minutes == 43200:
            return CronTrigger(
                day=day_of_month or 1,
                hour=schedule_hour,
                minute=schedule_minute,
                timezone=self.timezone,
            )
        return IntervalTrigger(minutes=interval_minutes, timezone=self.timezone)

    async def _sync_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            await self.sync_once()
            if self._lock_acquired and self._lock_file.exists():
                os.utime(self._lock_file, None)

    def _acquire_lock(self) -> bool:
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self._lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as handle:
                handle.write(f"{os.getpid()} {int(time.time())}\n")
            self._lock_acquired = True
            return True
        except FileExistsError:
            stale = False
            try:
                content = self._lock_file.read_text(encoding="utf-8").strip()
                pid_str = content.split()[0] if content else ""
                pid = int(pid_str) if pid_str else 0
            except (OSError, ValueError):
                pid = 0
            age = time.time() - self._lock_file.stat().st_mtime
            if age > self.settings.scheduler_lock_seconds:
                stale = True
            elif pid and not _pid_alive(pid):
                stale = True
            if stale:
                try:
                    self._lock_file.unlink()
                except OSError:
                    return False
                return self._acquire_lock()
            return False

    def _release_lock(self) -> None:
        if self._lock_acquired and self._lock_file.exists():
            self._lock_file.unlink()
        self._lock_acquired = False
