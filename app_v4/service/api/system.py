from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
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
    return StatusResponse(
        service="running",
        version=__version__,
        started_at=runtime.started_at,
        host=runtime.settings.service_host,
        port=runtime.settings.service_port,
    )


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> MetricsResponse:
    repo = Repository(session)
    values = await repo.system_metrics()
    return MetricsResponse(**values)
