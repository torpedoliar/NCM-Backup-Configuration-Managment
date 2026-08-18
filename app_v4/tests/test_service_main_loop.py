import asyncio

import pytest

from app_v4.core.crypto_service import CryptoService
from app_v4.data.repository import Repository
from app_v4.service.backup_service import BackupService
from app_v4.service.events import EventHub
from app_v4.service.main import _persistent_loop
from app_v4.service.scheduler import SchedulerService


def test_persistent_loop_stays_open_across_use():
    loop = _persistent_loop()
    assert not loop.is_closed()
    future = asyncio.run_coroutine_threadsafe(asyncio.sleep(0), loop)
    future.result(timeout=5)
    assert not loop.is_closed()


async def _seed_job(session_factory) -> None:
    async with session_factory() as session:
        repo = Repository(session)
        cred = await repo.create_credential("c", b"x")
        switch = await repo.create_switch("sw", "10.0.0.2", "ssh", 22, cred.id)
        await repo.create_job(switch.id, 1440, enabled=True, schedule_hour=22, schedule_minute=5)
        await session.commit()


def _new_scheduler_on(loop, settings, session_factory, crypto) -> SchedulerService:
    async def build() -> SchedulerService:
        scheduler = SchedulerService(
            settings,
            session_factory,
            BackupService(settings, session_factory, crypto, event_hub=EventHub()),
            event_hub=EventHub(),
        )
        scheduler.scheduler.start()
        return scheduler

    return asyncio.run_coroutine_threadsafe(build(), loop).result(timeout=15)


@pytest.mark.asyncio
async def test_scheduler_adds_jobs_when_runtime_built_off_loop(test_settings, session_factory):
    """Regression: the uvicorn factory built the runtime on a throwaway loop, so
    job additions from request handlers failed with 'Event loop is closed' and
    next-run times never appeared."""
    crypto = CryptoService(settings=test_settings, passphrase="p")
    await _seed_job(session_factory)

    loop = _persistent_loop()
    scheduler = _new_scheduler_on(loop, test_settings, session_factory, crypto)

    # simulate the API handler: runs on a different loop than the scheduler
    await scheduler.sync_once()
    snapshot = scheduler.status_snapshot()

    assert snapshot["jobs"], "job should be registered with the scheduler"
    assert snapshot["jobs"][0]["next_run_time"] is not None
    scheduler.scheduler.shutdown(wait=False)
