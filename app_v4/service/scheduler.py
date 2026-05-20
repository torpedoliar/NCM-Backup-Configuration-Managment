from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.core.paths import resolve_paths
from app_v4.data.repository import Repository
from app_v4.service.backup_service import BackupService
from app_v4.service.events import EventHub, publish
from app_v4.service.retention_service import RetentionService


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
        self.scheduler = AsyncIOScheduler(job_defaults={"coalesce": False, "max_instances": 3})
        self.job_map: dict[int, str] = {}
        self.job_interval_map: dict[int, int] = {}
        self.job_time_map: dict[int, tuple[int, int]] = {}
        self._sync_task: asyncio.Task | None = None
        self._lock_acquired = False
        self._lock_file = resolve_paths(settings).scheduler_lock_file

    async def start(self) -> bool:
        if not self._acquire_lock():
            return False
        self.scheduler.start()
        if self.retention_service is not None:
            self.scheduler.add_job(
                self.retention_service.run_once,
                CronTrigger(hour=self.settings.retention_hour, minute=self.settings.retention_minute),
                id="retention-nightly",
                replace_existing=True,
            )
        await self.sync_once()
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
        enabled_ids = {job.id for job in jobs if job.enabled}
        for job_id in list(self.job_map):
            if job_id not in enabled_ids:
                self.remove_job(job_id)
        for job in jobs:
            if not job.enabled:
                continue
            time_pair = (job.schedule_hour, job.schedule_minute)
            if job.id not in self.job_map:
                self.add_job(job.id, job.switch_id, job.interval_minutes, job.schedule_hour, job.schedule_minute)
            elif self.job_interval_map.get(job.id) != job.interval_minutes or self.job_time_map.get(job.id) != time_pair:
                self.remove_job(job.id)
                self.add_job(job.id, job.switch_id, job.interval_minutes, job.schedule_hour, job.schedule_minute)

    def add_job(self, job_id: int, switch_id: int, interval_minutes: int, schedule_hour: int, schedule_minute: int) -> None:
        aps_id = f"backup_job_{job_id}"
        self.scheduler.add_job(
            self.execute_scheduled_backup,
            trigger=self._build_trigger(interval_minutes, schedule_hour, schedule_minute),
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

    def _build_trigger(self, interval_minutes: int, schedule_hour: int, schedule_minute: int):
        if interval_minutes == 1440:
            return CronTrigger(hour=schedule_hour, minute=schedule_minute)
        if interval_minutes == 10080:
            return CronTrigger(day_of_week="mon", hour=schedule_hour, minute=schedule_minute)
        if interval_minutes == 43200:
            return CronTrigger(day=1, hour=schedule_hour, minute=schedule_minute)
        return IntervalTrigger(minutes=interval_minutes)

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
            age = time.time() - self._lock_file.stat().st_mtime
            if age > self.settings.scheduler_lock_seconds:
                self._lock_file.unlink()
                return self._acquire_lock()
            return False

    def _release_lock(self) -> None:
        if self._lock_acquired and self._lock_file.exists():
            self._lock_file.unlink()
        self._lock_acquired = False
