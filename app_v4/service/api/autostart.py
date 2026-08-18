from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app_v4.core.auth_service import AccessClaims
from app_v4.desktop.autostart import AutostartConfig, AutostartStatus
from app_v4.service.autostart_service import (
    disable_autostart,
    enable_autostart,
    query_status,
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


class AutostartUpdate(BaseModel):
    enabled: bool
    trigger: Literal["startup", "logon"] = "startup"


def _to_response(status: AutostartStatus, exe) -> AutostartStatusResponse:
    return AutostartStatusResponse(
        installed=status.installed,
        ready=status.ready,
        raw_status=status.raw_status,
        executable_path=str(exe) if exe is not None else None,
    )


@router.get("/autostart", response_model=AutostartStatusResponse)
async def get_autostart(
    _runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> AutostartStatusResponse:
    status = await query_status()
    return _to_response(status, resolve_executable_path())


@router.put("/autostart", response_model=AutostartStatusResponse)
async def put_autostart(
    payload: AutostartUpdate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> AutostartStatusResponse:
    if not payload.enabled:
        result = await disable_autostart()
        await runtime.audit_writer.record(
            action="system.autostart_disabled",
            user_id=user.user_id,
            ip=request.client.host if request.client else None,
        )
        return _to_response(result.status, resolve_executable_path())

    exe = resolve_executable_path()
    if exe is None:
        raise problem(
            422,
            "Unprocessable Entity",
            "Auto-start requires the bundled executable. Run NCM v4 from the installed app, not from source.",
        )
    config = AutostartConfig(
        executable=exe,
        run_at_startup=payload.trigger == "startup",
        run_at_logon=payload.trigger == "logon",
    )
    result = await enable_autostart(config)
    if not result.ok:
        raise problem(500, "Internal Server Error", result.message)
    await runtime.audit_writer.record(
        action="system.autostart_enabled",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={"trigger": payload.trigger},
    )
    return _to_response(result.status, exe)
