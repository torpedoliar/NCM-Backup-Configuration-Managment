from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime

from fastapi import APIRouter, Depends, Request

from app_v4.core.paths import resolve_paths
from app_v4.core.runtime_settings import load_runtime_settings, save_runtime_settings
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4 import __version__
from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/system", tags=["system"])


class StatusResponse(BaseModel):
    service: str
    version: str
    started_at: datetime
    host: str
    port: int
    uptime_seconds: int
    scheduler_running: bool
    db_size_bytes: int


class MetricsResponse(BaseModel):
    switches: int
    backups: int
    jobs: int
    failures_24h: int


class RetentionResponse(BaseModel):
    backup_min_keep: int
    backup_retention_days: int
    audit_retention_days: int
    retention_hour: int
    retention_minute: int


class RetentionPatch(BaseModel):
    backup_min_keep: int | None = Field(default=None, ge=1)
    backup_retention_days: int | None = Field(default=None, ge=7)
    audit_retention_days: int | None = Field(default=None, ge=7)
    retention_hour: int | None = Field(default=None, ge=0, le=23)
    retention_minute: int | None = Field(default=None, ge=0, le=59)


@router.get("/status", response_model=StatusResponse)
async def status(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> StatusResponse:
    paths = resolve_paths(runtime.settings)
    return StatusResponse(
        service="running",
        version=__version__,
        started_at=runtime.started_at,
        host=runtime.settings.service_host,
        port=runtime.settings.service_port,
        uptime_seconds=int((datetime.utcnow() - runtime.started_at).total_seconds()),
        scheduler_running=runtime.scheduler_service.scheduler.running if runtime.scheduler_service else False,
        db_size_bytes=paths.database_file.stat().st_size if paths.database_file.exists() else 0,
    )


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> MetricsResponse:
    repo = Repository(session)
    values = await repo.system_metrics()
    return MetricsResponse(
        switches=values["switches"],
        backups=values["backups"],
        jobs=values["jobs"],
        failures_24h=values["failed_backups"],
    )


@router.get("/retention", response_model=RetentionResponse)
async def get_retention(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> RetentionResponse:
    paths = resolve_paths(runtime.settings)
    rs = load_runtime_settings(paths.data_dir / "runtime_settings.json")
    return RetentionResponse(**asdict(rs.retention))


@router.patch("/retention", response_model=RetentionResponse)
async def patch_retention(
    payload: RetentionPatch,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> RetentionResponse:
    paths = resolve_paths(runtime.settings)
    target = paths.data_dir / "runtime_settings.json"
    current = load_runtime_settings(target)
    updates = payload.model_dump(exclude_none=True)
    new_retention = replace(current.retention, **updates)
    new_settings = replace(current, retention=new_retention)
    save_runtime_settings(target, new_settings)

    if runtime.scheduler_service is not None and (
        "retention_hour" in updates or "retention_minute" in updates
    ):
        runtime.scheduler_service.reschedule_retention(
            new_retention.retention_hour, new_retention.retention_minute
        )

    await runtime.audit_writer.record(
        action="system.retention_updated",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={"changes": updates},
    )
    return RetentionResponse(**asdict(new_retention))
