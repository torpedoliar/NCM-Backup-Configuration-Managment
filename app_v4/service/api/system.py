from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from app_v4.core.paths import resolve_paths
from pydantic import BaseModel
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
    failed_backups: int


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
    return MetricsResponse(**values)
