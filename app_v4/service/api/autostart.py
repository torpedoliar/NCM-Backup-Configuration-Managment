from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app_v4.core.auth_service import AccessClaims
from app_v4.desktop.autostart import AutostartConfig, AutostartMethod, AutostartStatus
from app_v4.service.autostart_service import (
    disable_autostart,
    enable_autostart,
    query_any_status,
    resolve_executable_path,
)
from app_v4.service.deps import get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/system", tags=["system"])


class AutostartStatusResponse(BaseModel):
    installed: bool
    ready: bool
    raw_status: str | None
    executable_path: str | None
    method: AutostartMethod | None = None


class AutostartUpdate(BaseModel):
    enabled: bool
    trigger: Literal["startup", "logon"] = "startup"
    method: AutostartMethod = "task"
    run_whether_logged_on: bool = False
    username: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, max_length=256)


def _to_response(status: AutostartStatus, exe, method: AutostartMethod | None = None) -> AutostartStatusResponse:
    return AutostartStatusResponse(
        installed=status.installed,
        ready=status.ready,
        raw_status=status.raw_status,
        executable_path=str(exe) if exe is not None else None,
        method=method,
    )


@router.get("/autostart", response_model=AutostartStatusResponse)
async def get_autostart(
    _runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> AutostartStatusResponse:
    status, method = await query_any_status()
    return _to_response(status, resolve_executable_path(), method)


@router.put("/autostart", response_model=AutostartStatusResponse)
async def put_autostart(
    payload: AutostartUpdate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> AutostartStatusResponse:
    if not payload.enabled:
        result = await disable_autostart(method=payload.method)
        await runtime.audit_writer.record(
            action="system.autostart_disabled",
            user_id=user.user_id,
            ip=request.client.host if request.client else None,
            detail={"method": payload.method},
        )
        return _to_response(result.status, resolve_executable_path())

    exe = resolve_executable_path()
    if exe is None:
        raise problem(
            422,
            "Unprocessable Entity",
            "Auto-start requires the bundled executable. Run NCM v4 from the installed app, not from source.",
        )
    if payload.method == "task" and payload.run_whether_logged_on and not (payload.username and payload.password):
        raise problem(
            422,
            "Unprocessable Entity",
            "Running without a logged-on user requires a username and password.",
        )
    config = AutostartConfig(
        executable=exe,
        run_at_startup=payload.trigger == "startup",
        run_at_logon=payload.trigger == "logon",
        method=payload.method,
        run_whether_logged_on=payload.run_whether_logged_on,
        username=payload.username,
        password=payload.password,
    )
    result = await enable_autostart(config)
    if not result.ok:
        raise problem(500, "Internal Server Error", result.message)
    await runtime.audit_writer.record(
        action="system.autostart_enabled",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={
            "trigger": payload.trigger,
            "method": payload.method,
            "run_whether_logged_on": payload.run_whether_logged_on,
        },
    )
    return _to_response(result.status, exe, payload.method)
