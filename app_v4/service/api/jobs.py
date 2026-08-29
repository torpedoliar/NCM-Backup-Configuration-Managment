from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.core.utcdatetime import utc_now
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.events import publish
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime
from app_v4.service.timeutil import to_aware_utc

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: int
    switch_id: int
    name: str
    interval_minutes: int
    enabled: bool
    schedule_hour: int
    schedule_minute: int
    day_of_week: str | None = None
    day_of_month: int | None = None
    last_run_at: datetime | None = None


class JobCreate(BaseModel):
    switch_id: int
    name: str | None = None
    interval_minutes: int = Field(gt=0)
    enabled: bool = True
    schedule_hour: int = Field(default=8, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)
    day_of_week: str | None = None
    day_of_month: int | None = None


class JobUpdate(BaseModel):
    name: str | None = None
    interval_minutes: int | None = Field(default=None, gt=0)
    enabled: bool | None = None
    schedule_hour: int | None = Field(default=None, ge=0, le=23)
    schedule_minute: int | None = Field(default=None, ge=0, le=59)
    day_of_week: str | None = None
    day_of_month: int | None = None


def _to_out(job) -> JobOut:
    switch_name = job.switch.name if getattr(job, "switch", None) is not None else f"job-{job.id}"
    return JobOut(
        id=job.id,
        switch_id=job.switch_id,
        name=job.name or switch_name,
        interval_minutes=job.interval_minutes,
        enabled=job.enabled,
        schedule_hour=job.schedule_hour,
        schedule_minute=job.schedule_minute,
        day_of_week=job.day_of_week,
        day_of_month=job.day_of_month,
        last_run_at=to_aware_utc(job.last_ran_at),
    )


async def _resync_scheduler(runtime: ServiceRuntime) -> None:
    """Reflect job changes to APScheduler immediately.

    Without this, the periodic _sync_loop (30s tick) is the only path that
    re-arms triggers, so a freshly-edited 11:05 job may stay armed at the
    previous time for up to 30 seconds — and if a clock interaction happens
    in that window, miss its first fire entirely.

    Sync errors are swallowed: the row was already saved by the caller, and
    the periodic loop will try again on the next tick. Bubbling here would
    surface as a 500 even though the persisted job is correct.
    """
    if runtime.scheduler_service is None:
        return
    try:
        await runtime.scheduler_service.sync_once()
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "scheduler resync after job change failed", exc_info=True
        )


@router.get("", response_model=list[JobOut])
async def list_jobs(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[JobOut]:
    repo = Repository(session)
    return [_to_out(j) for j in await repo.list_jobs()]


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> JobOut:
    repo = Repository(session)
    switch = await repo.get_switch(payload.switch_id)
    if switch is None:
        raise problem(422, "Unprocessable Entity", "Referenced switch does not exist")
    job = await repo.create_job(
        switch_id=payload.switch_id,
        name=payload.name or switch.name,
        interval_minutes=payload.interval_minutes,
        enabled=payload.enabled,
        schedule_hour=payload.schedule_hour,
        schedule_minute=payload.schedule_minute,
        day_of_week=payload.day_of_week,
        day_of_month=payload.day_of_month,
    )
    await session.commit()
    job = await repo.get_job(job.id)
    await runtime.audit_writer.record(
        action="schedule.created",
        user_id=actor.user_id,
        target_type="job",
        target_id=str(job.id),
        ip=request.client.host if request.client else None,
        detail=payload.model_dump(),
    )
    await _resync_scheduler(runtime)
    return _to_out(job)


@router.post("/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_job_now(
    job_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    user: AccessClaims = Depends(require_role("admin", "operator")),
) -> dict:
    repo = Repository(session)
    job = await repo.get_job(job_id)
    if job is None:
        raise problem(404, "Not Found", "Job not found")
    if runtime.backup_service is None:
        raise problem(503, "Service Unavailable", "Backup service is not initialized")
    # Audit captures intent (admin clicked run-now); backup outcome is recorded
    # in the Backup table by execute_backup.
    await runtime.audit_writer.record(
        action="schedule.run_now",
        user_id=user.user_id,
        target_type="job",
        target_id=str(job_id),
        ip=request.client.host if request.client else None,
    )
    started_at = utc_now()
    await publish(
        runtime.event_hub,
        "job_triggered",
        {"job_id": job_id, "switch_id": job.switch_id},
    )
    result = await runtime.backup_service.execute_backup(
        switch_id=job.switch_id,
        backup_type="manual_schedule",
        job_id=job_id,
        triggered_by_user_id=user.user_id,
    )
    await Repository(session).update_job(job_id, last_ran_at=started_at)
    await session.commit()
    return {"backup_id": result.get("backup_id"), "success": result.get("success")}


@router.patch("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: int,
    payload: JobUpdate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> JobOut:
    repo = Repository(session)
    changes = payload.model_dump(exclude_unset=True)
    job = await repo.update_job(job_id, **changes)
    if job is None:
        raise problem(404, "Not Found", "Job not found")
    await session.commit()
    await runtime.audit_writer.record(
        action="schedule.updated",
        user_id=actor.user_id,
        target_type="job",
        target_id=str(job_id),
        ip=request.client.host if request.client else None,
        detail=changes,
    )
    await _resync_scheduler(runtime)
    return _to_out(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> Response:
    repo = Repository(session)
    deleted = await repo.delete_job(job_id)
    if not deleted:
        raise problem(404, "Not Found", "Job not found")
    await session.commit()
    await runtime.audit_writer.record(
        action="schedule.deleted",
        user_id=actor.user_id,
        target_type="job",
        target_id=str(job_id),
        ip=request.client.host if request.client else None,
    )
    await _resync_scheduler(runtime)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
