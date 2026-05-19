from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.diff_service import DiffService
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(tags=["backups"])


class BackupOut(BaseModel):
    id: int
    switch_id: int
    file_path: str
    content_hash: str
    size_bytes: int
    success: bool
    message: str | None
    backup_type: str


class BackupRunResponse(BaseModel):
    success: bool
    message: str
    file_path: str
    size_kb: float
    backup_id: int


def _to_out(backup) -> BackupOut:
    return BackupOut(
        id=backup.id,
        switch_id=backup.switch_id,
        file_path=backup.file_path,
        content_hash=backup.content_hash,
        size_bytes=backup.size_bytes,
        success=backup.success,
        message=backup.message,
        backup_type=backup.backup_type,
    )


async def _run_backup(runtime: ServiceRuntime, switch_id: int, user_id: int, request: Request) -> BackupRunResponse:
    if runtime.backup_service is None:
        raise problem(503, "Service Unavailable", "Backup service is not initialized")
    try:
        result = await runtime.backup_service.execute_backup(
            switch_id=switch_id,
            backup_type="manual",
            triggered_by_user_id=user_id,
        )
    except ValueError as exc:
        raise problem(404, "Not Found", str(exc)) from exc
    await runtime.audit_writer.record(
        action="backup.manual_triggered",
        user_id=user_id,
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
        detail={
            "switch_id": switch_id,
            "backup_id": result.get("backup_id"),
            "success": result.get("success"),
        },
    )
    return BackupRunResponse(**result)


@router.post("/switches/{switch_id}/backup", response_model=BackupRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_backup_spec_alias(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin", "operator")),
) -> BackupRunResponse:
    return await _run_backup(runtime, switch_id, user.user_id, request)


@router.post("/switches/{switch_id}/backups", response_model=BackupRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_backup(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin", "operator")),
) -> BackupRunResponse:
    return await _run_backup(runtime, switch_id, user.user_id, request)


@router.get("/backups", response_model=list[BackupOut])
async def list_backups(
    switch_id: int | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[BackupOut]:
    repo = Repository(session)
    return [_to_out(b) for b in await repo.list_backups(switch_id=switch_id, limit=limit)]


@router.get("/backups/diff")
async def diff_backups(
    a: int,
    b: int,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> Response:
    repo = Repository(session)
    left = await repo.get_backup(a)
    right = await repo.get_backup(b)
    if left is None or right is None:
        raise problem(404, "Not Found", "One or both backups were not found")
    left_path = Path(left.file_path or "")
    right_path = Path(right.file_path or "")
    if not left_path.exists() or not right_path.exists():
        raise problem(404, "Not Found", "One or both backup files were not found")
    diff = DiffService(runtime.settings).unified_diff(
        left_path.read_text(encoding="utf-8"),
        right_path.read_text(encoding="utf-8"),
        label1=f"backup-{a}",
        label2=f"backup-{b}",
    )
    return Response(diff, media_type="text/plain")


@router.get("/backups/{backup_id}", response_model=BackupOut)
async def get_backup(
    backup_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> BackupOut:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    return _to_out(backup)


@router.get("/backups/{backup_id}/content")
async def get_backup_content(
    backup_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> Response:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    path = Path(backup.file_path)
    if not path.exists():
        raise problem(404, "Not Found", "Backup file not found")
    return Response(path.read_text(encoding="utf-8"), media_type="text/plain")


@router.get("/backups/{backup_id}/diff")
async def get_backup_diff(
    backup_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> Response:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    diff_path = Path(str(backup.file_path).rsplit(".txt", 1)[0] + ".diff")
    if not diff_path.exists():
        raise problem(404, "Not Found", "Diff file not found")
    return Response(diff_path.read_text(encoding="utf-8"), media_type="text/plain")
