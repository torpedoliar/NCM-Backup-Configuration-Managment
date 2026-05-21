from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request

from app_v4.core.logging import LOG_FILE_NAME
from app_v4.core.paths import resolve_paths
from app_v4.core.runtime_settings import load_runtime_settings, save_runtime_settings
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4 import __version__
from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.log_tail import LogLine, tail_log
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
    data_dir: str
    backups_dir: str
    logs_dir: str


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


class AuthSettingsResponse(BaseModel):
    access_token_minutes: int
    refresh_token_days: int
    lockout_threshold: int
    lockout_window_minutes: int
    lockout_duration_minutes: int
    password_min_length: int
    password_require_upper: bool
    password_require_lower: bool
    password_require_digit: bool
    password_require_symbol: bool


class AuthSettingsPatch(BaseModel):
    access_token_minutes: int | None = Field(default=None, ge=5, le=1440)
    refresh_token_days: int | None = Field(default=None, ge=1, le=30)
    lockout_threshold: int | None = Field(default=None, ge=0, le=20)
    lockout_window_minutes: int | None = Field(default=None, ge=1, le=60)
    lockout_duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    password_min_length: int | None = Field(default=None, ge=6, le=128)
    password_require_upper: bool | None = None
    password_require_lower: bool | None = None
    password_require_digit: bool | None = None
    password_require_symbol: bool | None = None


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
        data_dir=str(paths.data_dir),
        backups_dir=str(paths.backups_dir),
        logs_dir=str(paths.logs_dir),
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


@router.get("/auth-settings", response_model=AuthSettingsResponse)
async def get_auth_settings(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin")),
) -> AuthSettingsResponse:
    paths = resolve_paths(runtime.settings)
    rs = load_runtime_settings(paths.data_dir / "runtime_settings.json")
    return AuthSettingsResponse(**asdict(rs.auth))


@router.patch("/auth-settings", response_model=AuthSettingsResponse)
async def patch_auth_settings(
    payload: AuthSettingsPatch,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> AuthSettingsResponse:
    paths = resolve_paths(runtime.settings)
    target = paths.data_dir / "runtime_settings.json"
    current = load_runtime_settings(target)
    updates = payload.model_dump(exclude_none=True)
    new_auth = replace(current.auth, **updates)
    save_runtime_settings(target, replace(current, auth=new_auth))
    await runtime.audit_writer.record(
        action="system.auth_settings_updated",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={"changes": updates},
    )
    return AuthSettingsResponse(**asdict(new_auth))


def _resolve_log_file(runtime: ServiceRuntime) -> Path:
    return resolve_paths(runtime.settings).logs_dir / LOG_FILE_NAME


class LogsResponse(BaseModel):
    lines: list[dict[str, str]]
    total_returned: int
    log_file: str
    log_file_size_bytes: int


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    request: Request,
    lines: int = Query(default=200, ge=1, le=5000),
    level: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> LogsResponse:
    log_path = _resolve_log_file(runtime)
    parsed = tail_log(log_path, lines=lines, level=level, q=q, since=since)
    await runtime.audit_writer.record(
        action="system.logs_viewed",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={"lines": lines, "level": level, "q": q},
    )
    return LogsResponse(
        lines=[{"ts": l.ts, "level": l.level, "logger": l.logger, "message": l.message} for l in parsed],
        total_returned=len(parsed),
        log_file=str(log_path),
        log_file_size_bytes=log_path.stat().st_size if log_path.exists() else 0,
    )
