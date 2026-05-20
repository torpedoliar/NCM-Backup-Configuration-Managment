from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: int
    switch_id: int
    name: str
    interval_minutes: int
    enabled: bool
    schedule_hour: int
    schedule_minute: int
    last_run_at: datetime | None = None


class JobCreate(BaseModel):
    switch_id: int
    interval_minutes: int = Field(gt=0)
    enabled: bool = True
    schedule_hour: int = Field(default=8, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)


class JobUpdate(BaseModel):
    interval_minutes: int | None = Field(default=None, gt=0)
    enabled: bool | None = None
    schedule_hour: int | None = Field(default=None, ge=0, le=23)
    schedule_minute: int | None = Field(default=None, ge=0, le=59)


def _to_out(job) -> JobOut:
    switch_name = job.switch.name if getattr(job, "switch", None) is not None else f"job-{job.id}"
    return JobOut(
        id=job.id,
        switch_id=job.switch_id,
        name=switch_name,
        interval_minutes=job.interval_minutes,
        enabled=job.enabled,
        schedule_hour=job.schedule_hour,
        schedule_minute=job.schedule_minute,
        last_run_at=job.last_ran_at,
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
    if await repo.get_switch(payload.switch_id) is None:
        raise problem(422, "Unprocessable Entity", "Referenced switch does not exist")
    job = await repo.create_job(payload.switch_id, payload.interval_minutes, payload.enabled, payload.schedule_hour, payload.schedule_minute)
    await session.commit()
    job = await repo.get_job(job.id)
    await runtime.audit_writer.record(
        action="job.created",
        user_id=actor.user_id,
        target_type="job",
        target_id=str(job.id),
        ip=request.client.host if request.client else None,
        detail=payload.model_dump(),
    )
    return _to_out(job)


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
    changes = payload.model_dump(exclude_none=True)
    job = await repo.update_job(job_id, **changes)
    if job is None:
        raise problem(404, "Not Found", "Job not found")
    await session.commit()
    await runtime.audit_writer.record(
        action="job.updated",
        user_id=actor.user_id,
        target_type="job",
        target_id=str(job_id),
        ip=request.client.host if request.client else None,
        detail=changes,
    )
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
        action="job.deleted",
        user_id=actor.user_id,
        target_type="job",
        target_id=str(job_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
