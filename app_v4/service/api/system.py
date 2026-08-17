from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request

from app_v4.core.logging import LOG_FILE_NAME
from app_v4.core.paths import resolve_paths
from app_v4.core.runtime_settings import BackupLocationSettings, TimeSettings, load_runtime_settings, save_runtime_settings
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4 import __version__
from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.log_tail import LogLine, tail_log
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime
from app_v4.service.timeutil import to_aware_utc

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


class BackupLocationResponse(BaseModel):
    backup_root_folder: str
    resolved_backups_dir: str


class BackupLocationPatch(BaseModel):
    backup_root_folder: str = Field(min_length=1)

    @field_validator("backup_root_folder")
    @classmethod
    def validate_backup_root_folder(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or "\x00" in cleaned:
            raise ValueError("Backup location must be a non-empty path")
        return cleaned


@router.get("/status", response_model=StatusResponse)
async def status(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> StatusResponse:
    paths = resolve_paths(runtime.settings)
    return StatusResponse(
        service="running",
        version=__version__,
        started_at=to_aware_utc(runtime.started_at),
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
    async with runtime.runtime_settings_lock:
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


@router.get("/backup-location", response_model=BackupLocationResponse)
async def get_backup_location(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> BackupLocationResponse:
    paths = resolve_paths(runtime.settings)
    return BackupLocationResponse(
        backup_root_folder=runtime.settings.backup_root_folder,
        resolved_backups_dir=str(paths.backups_dir),
    )


@router.patch("/backup-location", response_model=BackupLocationResponse)
async def patch_backup_location(
    payload: BackupLocationPatch,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> BackupLocationResponse:
    paths = resolve_paths(runtime.settings)
    target = paths.data_dir / "runtime_settings.json"
    async with runtime.runtime_settings_lock:
        current = load_runtime_settings(target)
        new_location = BackupLocationSettings(backup_root_folder=payload.backup_root_folder)
        candidate_settings = runtime.settings.model_copy(update={"backup_root_folder": payload.backup_root_folder})
        candidate_paths = resolve_paths(candidate_settings)
        probe_path: Path | None = None
        try:
            candidate_paths.backups_dir.mkdir(parents=True, exist_ok=True)
            probe_path = candidate_paths.backups_dir / f".ncm-v4-write-test-{uuid4().hex}"
            probe_path.write_text("ok", encoding="utf-8")
        except OSError as exc:
            raise problem(
                422,
                "Unprocessable Entity",
                f"Backup location is not writable: {candidate_paths.backups_dir}",
            ) from exc
        finally:
            if probe_path is not None:
                probe_path.unlink(missing_ok=True)

        save_runtime_settings(target, replace(current, backup_location=new_location))
        runtime.settings = candidate_settings
        if runtime.backup_service is not None:
            # BackupService is constructed once at startup. Keep its path
            # settings in sync with the live runtime so the next backup is
            # written where the API reports it will be written.
            runtime.backup_service.settings = runtime.settings
            if hasattr(runtime.backup_service.diff_service, "settings"):
                runtime.backup_service.diff_service.settings = runtime.settings
        paths = candidate_paths
    await runtime.audit_writer.record(
        action="system.backup_location_updated",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={"backup_root_folder": payload.backup_root_folder},
    )
    return BackupLocationResponse(
        backup_root_folder=runtime.settings.backup_root_folder,
        resolved_backups_dir=str(paths.backups_dir),
    )


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
    async with runtime.runtime_settings_lock:
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


class TimeSettingsResponse(BaseModel):
    timezone: str
    ntp_servers: list[str]
    ntp_enabled: bool
    available_timezones: list[str]
    server_now_utc: datetime
    server_now_local: datetime


class TimeSettingsPatch(BaseModel):
    timezone: str | None = Field(default=None, min_length=1)
    ntp_servers: list[str] | None = None
    ntp_enabled: bool | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("timezone must be non-empty")
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(cleaned)
        except Exception as exc:  # ZoneInfoNotFoundError, others
            raise ValueError(f"Unknown timezone: {cleaned}") from exc
        return cleaned

    @field_validator("ntp_servers")
    @classmethod
    def validate_ntp(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [s.strip() for s in value if s and s.strip()]
        if not cleaned:
            raise ValueError("ntp_servers must contain at least one non-empty entry")
        return cleaned


_COMMON_TIMEZONES = [
    "UTC",
    "Asia/Jakarta",
    "Asia/Makassar",
    "Asia/Jayapura",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Asia/Shanghai",
    "Asia/Kolkata",
    "Asia/Dubai",
    "Europe/London",
    "Europe/Berlin",
    "America/New_York",
    "America/Los_Angeles",
    "Australia/Sydney",
]


def _build_time_response(runtime: ServiceRuntime) -> TimeSettingsResponse:
    paths = resolve_paths(runtime.settings)
    rs = load_runtime_settings(paths.data_dir / "runtime_settings.json")
    from zoneinfo import ZoneInfo
    try:
        tz = ZoneInfo(rs.time.timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now(tz)
    return TimeSettingsResponse(
        timezone=rs.time.timezone,
        ntp_servers=list(rs.time.ntp_servers),
        ntp_enabled=rs.time.ntp_enabled,
        available_timezones=_COMMON_TIMEZONES,
        server_now_utc=now_utc,
        server_now_local=now_local,
    )


@router.get("/time-settings", response_model=TimeSettingsResponse)
async def get_time_settings(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> TimeSettingsResponse:
    return _build_time_response(runtime)


@router.patch("/time-settings", response_model=TimeSettingsResponse)
async def patch_time_settings(
    payload: TimeSettingsPatch,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> TimeSettingsResponse:
    paths = resolve_paths(runtime.settings)
    target = paths.data_dir / "runtime_settings.json"
    updates = payload.model_dump(exclude_none=True)
    async with runtime.runtime_settings_lock:
        current = load_runtime_settings(target)
        new_time = TimeSettings(
            timezone=updates.get("timezone", current.time.timezone),
            ntp_servers=tuple(updates.get("ntp_servers", current.time.ntp_servers)),
            ntp_enabled=updates.get("ntp_enabled", current.time.ntp_enabled),
        )
        save_runtime_settings(target, replace(current, time=new_time))
        if runtime.scheduler_service is not None:
            runtime.scheduler_service.reload_timezone()
    await runtime.audit_writer.record(
        action="system.time_settings_updated",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={"changes": updates},
    )
    return _build_time_response(runtime)


class RetentionRunResponse(BaseModel):
    audit_deleted: int
    backups_deleted: int
    backup_files_deleted: int


@router.post("/retention/run", response_model=RetentionRunResponse)
async def run_retention_now(
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> RetentionRunResponse:
    if runtime.retention_service is None:
        raise problem(503, "Service Unavailable", "Retention service is not initialized")
    result = await runtime.retention_service.run_once()
    await runtime.audit_writer.record(
        action="system.retention_run_now",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail=result,
    )
    return RetentionRunResponse(
        audit_deleted=int(result.get("audit_deleted", 0)),
        backups_deleted=int(result.get("backups_deleted", 0)),
        backup_files_deleted=int(result.get("backup_files_deleted", 0)),
    )


class SchedulerJobInfo(BaseModel):
    job_id: int
    next_run_time: str | None
    trigger: str | None


class SchedulerStatusResponse(BaseModel):
    running: bool
    timezone: str
    lock_acquired: bool
    lock_file: str
    jobs: list[SchedulerJobInfo]


@router.get("/scheduler-status", response_model=SchedulerStatusResponse)
async def scheduler_status(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> SchedulerStatusResponse:
    if runtime.scheduler_service is None:
        return SchedulerStatusResponse(
            running=False,
            timezone="UTC",
            lock_acquired=False,
            lock_file="",
            jobs=[],
        )
    snap = runtime.scheduler_service.status_snapshot()
    return SchedulerStatusResponse(
        running=bool(snap.get("running")),
        timezone=str(snap.get("timezone", "UTC")),
        lock_acquired=bool(snap.get("lock_acquired")),
        lock_file=str(snap.get("lock_file", "")),
        jobs=[SchedulerJobInfo(**j) for j in snap.get("jobs", [])],
    )
