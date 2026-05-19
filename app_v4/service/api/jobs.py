from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, require_role
from app_v4.service.problem import problem

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: int
    switch_id: int
    interval_minutes: int
    enabled: bool
    schedule_hour: int
    schedule_minute: int


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
    return JobOut(
        id=job.id,
        switch_id=job.switch_id,
        interval_minutes=job.interval_minutes,
        enabled=job.enabled,
        schedule_hour=job.schedule_hour,
        schedule_minute=job.schedule_minute,
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
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator")),
) -> JobOut:
    repo = Repository(session)
    if await repo.get_switch(payload.switch_id) is None:
        raise problem(422, "Unprocessable Entity", "Referenced switch does not exist")
    job = await repo.create_job(payload.switch_id, payload.interval_minutes, payload.enabled, payload.schedule_hour, payload.schedule_minute)
    await session.commit()
    return _to_out(job)


@router.patch("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: int,
    payload: JobUpdate,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator")),
) -> JobOut:
    repo = Repository(session)
    job = await repo.update_job(job_id, **payload.model_dump(exclude_none=True))
    if job is None:
        raise problem(404, "Not Found", "Job not found")
    await session.commit()
    return _to_out(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator")),
) -> Response:
    repo = Repository(session)
    deleted = await repo.delete_job(job_id)
    if not deleted:
        raise problem(404, "Not Found", "Job not found")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
