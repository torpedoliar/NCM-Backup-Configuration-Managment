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


def test_sync_mutations_dispatch_across_threads(test_settings, session_factory):
    """Regression: calling scheduler mutations (add_job/remove_job) from a
    different event-loop thread used to mutate the in-memory job store with no
    synchronization — risking ConflictingIdError/JobLookupError or dropped jobs.
    Now every mutation is confined to the scheduler's own loop."""
    import threading

    from app_v4.core.crypto_service import CryptoService

    crypto = CryptoService(settings=test_settings, passphrase="p")
    loop = _persistent_loop()

    def _seed():
        asyncio.run_coroutine_threadsafe(_seed_job(session_factory), loop).result(timeout=15)

    _seed()
    scheduler = _new_scheduler_on(loop, test_settings, session_factory, crypto)
    # build_runtime() calls SchedulerService.start() which captures the runtime
    # loop; replicate that here (the helper starts APS directly instead).
    scheduler._loop = loop
    assert scheduler._loop is not None

    # Arm the seeded job on the scheduler loop first so job_map is non-empty.
    asyncio.run_coroutine_threadsafe(scheduler.sync_once(), loop).result(timeout=15)
    assert scheduler.job_map, "job should be armed before the cross-thread phase"

    # Simulate an HTTP-handler thread: run add_job/remove_job from a separate
    # thread that is NOT the scheduler loop thread and not the current asyncio
    # loop. These must dispatch to the scheduler loop without deadlocking.
    result_holder = []

    def _handler():
        scheduler.remove_job(list(scheduler.job_map)[0])
        # Synthetic job: exercising that cross-thread add_job does not raise.
        scheduler.add_job(99999, 1, 60, 8, 30)
        result_holder.append("mutated")

    handler = threading.Thread(target=_handler)
    handler.start()
    handler.join(timeout=15)
    assert not handler.is_alive(), "cross-thread scheduler call deadlocked"
    assert result_holder == ["mutated"], "cross-thread mutation did not complete"

    scheduler.scheduler.shutdown(wait=False)
