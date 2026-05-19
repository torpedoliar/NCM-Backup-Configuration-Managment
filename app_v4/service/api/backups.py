from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
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


@router.post("/switches/{switch_id}/backups", response_model=BackupRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_backup(
    switch_id: int,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin", "operator")),
) -> BackupRunResponse:
    if runtime.backup_service is None:
        raise problem(503, "Service Unavailable", "Backup service is not initialized")
    result = await runtime.backup_service.execute_backup(
        switch_id=switch_id,
        backup_type="manual",
        triggered_by_user_id=user.user_id,
    )
    return BackupRunResponse(**result)


@router.get("/backups", response_model=list[BackupOut])
async def list_backups(
    switch_id: int | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[BackupOut]:
    repo = Repository(session)
    return [_to_out(b) for b in await repo.list_backups(switch_id=switch_id, limit=limit)]


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
