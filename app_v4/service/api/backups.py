from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.core.utcdatetime import utc_now
from app_v4.data.repository import Repository
from app_v4.net.config_parsers import detect_dialect, parse_config
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.diff_service import DiffService
from app_v4.service.problem import problem
from app_v4.service.reporting import (
    BackupReportRow,
    render_csv,
    render_pdf,
    render_xlsx,
)
from app_v4.service.runtime import ServiceRuntime
from app_v4.service.backup_service import SwitchInactiveError
from app_v4.service.timeutil import to_aware_utc

logger = logging.getLogger(__name__)

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
    created_at: datetime


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
        created_at=to_aware_utc(backup.taken_at),
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
    except SwitchInactiveError as exc:
        raise problem(409, "Conflict", str(exc)) from exc
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
    response: Response,
    switch_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    success: bool | None = None,
    backup_type: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[BackupOut]:
    repo = Repository(session)
    total = await repo.count_backups(
        switch_id=switch_id,
        success=success,
        backup_type=backup_type,
        from_ts=from_ts,
        to_ts=to_ts,
        q=q,
    )
    response.headers["X-Total-Count"] = str(total)
    return [
        _to_out(b)
        for b in await repo.list_backups(
            switch_id=switch_id,
            limit=limit,
            offset=offset,
            success=success,
            backup_type=backup_type,
            from_ts=from_ts,
            to_ts=to_ts,
            q=q,
        )
    ]


@router.get("/backups/latest-per-switch", response_model=list[BackupOut])
async def latest_backup_per_switch(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[BackupOut]:
    """Newest successful backup for every switch (server-side grouping).

    Declared before ``/backups/{backup_id}`` so the literal path wins.
    """
    repo = Repository(session)
    return [_to_out(b) for b in await repo.latest_backup_per_switch(only_success=True)]


@router.get("/backups/report")
async def export_backups_report(
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
    switch_id: int | None = None,
    success: bool | None = None,
    backup_type: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    q: str | None = None,
    limit: int = Query(default=5000, ge=1, le=20000),
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> Response:
    repo = Repository(session)
    rows = await repo.list_backups(
        switch_id=switch_id,
        limit=limit,
        success=success,
        backup_type=backup_type,
        from_ts=from_ts,
        to_ts=to_ts,
        q=q,
    )
    switch_ids = {row.switch_id for row in rows}
    name_by_id: dict[int, str] = {}
    for sid in switch_ids:
        sw = await repo.get_switch(sid)
        if sw is not None:
            name_by_id[sid] = sw.name
    report_rows = [
        BackupReportRow(
            id=row.id,
            switch_name=name_by_id.get(row.switch_id, f"#{row.switch_id}"),
            taken_at=row.taken_at,
            backup_type=row.backup_type,
            success=row.success,
            size_bytes=row.size_bytes or 0,
            message=row.message or "",
        )
        for row in rows
    ]
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    if format == "csv":
        body = render_csv(report_rows)
        filename = f"backups-{stamp}.csv"
        media = "text/csv; charset=utf-8"
    elif format == "xlsx":
        body = render_xlsx(report_rows)
        filename = f"backups-{stamp}.xlsx"
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        body = render_pdf(report_rows)
        filename = f"backups-{stamp}.pdf"
        media = "application/pdf"
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    try:
        left_text = left_path.read_text(encoding="utf-8")
        right_text = right_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise problem(404, "Not Found", "One or both backup files were not found") from exc
    except UnicodeDecodeError as exc:
        raise problem(422, "Unprocessable Entity", "One or both backup files are not UTF-8 text") from exc
    diff = DiffService(runtime.settings).unified_diff(
        left_text,
        right_text,
        label1=f"backup-{a}",
        label2=f"backup-{b}",
    )
    if not diff:
        diff = "No changes.\n"
    return Response(diff, media_type="text/plain; charset=utf-8")


class SideBySideRow(BaseModel):
    line_a: int
    line_b: int
    text_a: str
    text_b: str
    op: str


class DiffStats(BaseModel):
    added_lines: int
    removed_lines: int
    changed_lines: int
    total_changes: int


class SideBySideResponse(BaseModel):
    rows: list[SideBySideRow]
    stats: DiffStats


@router.get("/backups/diff/side-by-side", response_model=SideBySideResponse)
async def diff_backups_side_by_side(
    a: int,
    b: int,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> SideBySideResponse:
    repo = Repository(session)
    left = await repo.get_backup(a)
    right = await repo.get_backup(b)
    if left is None or right is None:
        raise problem(404, "Not Found", "One or both backups were not found")
    left_path = Path(left.file_path or "")
    right_path = Path(right.file_path or "")
    if not left_path.exists() or not right_path.exists():
        raise problem(404, "Not Found", "One or both backup files were not found")
    try:
        left_text = left_path.read_text(encoding="utf-8")
        right_text = right_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise problem(404, "Not Found", "One or both backup files were not found") from exc
    except UnicodeDecodeError as exc:
        raise problem(422, "Unprocessable Entity", "One or both backup files are not UTF-8 text") from exc
    service = DiffService(runtime.settings)
    rows = service.side_by_side_diff(left_text, right_text)
    stats = service.get_diff_stats(left_text, right_text)
    return SideBySideResponse(
        rows=[
            SideBySideRow(line_a=la, line_b=lb, text_a=ta, text_b=tb, op=op)
            for (la, lb, ta, tb, op) in rows
        ],
        stats=DiffStats(**stats),
    )


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
    download: bool = False,
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
    headers: dict[str, str] = {}
    if download:
        switch = await repo.get_switch(backup.switch_id)
        switch_name = switch.name if switch is not None else f"switch-{backup.switch_id}"
        ts = backup.taken_at.strftime("%Y%m%dT%H%M%S")
        filename = f"{switch_name}_{ts}.txt".replace(" ", "_")
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(path.read_text(encoding="utf-8"), media_type="text/plain", headers=headers)


class DecodeVlan(BaseModel):
    id: int
    name: str | None


class DecodePort(BaseModel):
    name: str
    description: str | None
    enabled: bool
    mode: str
    native_vlan: int | None
    access_vlan: int | None
    trunk_allowed_vlans: list[int]


class DecodedBackupOut(BaseModel):
    backup_id: int
    switch_id: int
    switch_name: str
    protocol: str
    dialect: str
    hostname: str | None
    backup_taken_at: datetime | None
    vlans: list[DecodeVlan]
    ports: list[DecodePort]
    parse_warnings: list[str]


@router.get("/backups/{backup_id}/decode", response_model=DecodedBackupOut)
async def decode_backup(
    backup_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> DecodedBackupOut:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    path = Path(backup.file_path or "")
    if not path.is_file():
        raise problem(404, "Not Found", "Backup file not found")
    switch = await repo.get_switch(backup.switch_id)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise problem(422, "Unprocessable Entity", "Backup file is not readable UTF-8 text") from exc
    cfg = parse_config(text)
    return DecodedBackupOut(
        backup_id=backup.id,
        switch_id=backup.switch_id,
        switch_name=switch.name if switch else f"#{backup.switch_id}",
        protocol=switch.protocol if switch else "",
        dialect=detect_dialect(text),
        hostname=cfg.hostname,
        backup_taken_at=to_aware_utc(backup.taken_at),
        vlans=[DecodeVlan(id=v.id, name=v.name) for v in cfg.vlans],
        ports=[
            DecodePort(
                name=p.name,
                description=p.description,
                enabled=p.enabled,
                mode=p.mode,
                native_vlan=p.native_vlan,
                access_vlan=p.access_vlan,
                trunk_allowed_vlans=p.trunk_allowed_vlans,
            )
            for p in cfg.ports
        ],
        parse_warnings=cfg.warnings,
    )


@router.delete("/backups/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backup(
    backup_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> Response:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    file_path = backup.file_path
    await repo.delete_backup(backup_id)
    await session.commit()
    file_unlinked = False
    if file_path:
        try:
            Path(file_path).unlink(missing_ok=True)
            file_unlinked = True
        except OSError as exc:
            logger.warning("backup file unlink failed: %s (path=%s)", exc, file_path)
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="backup.deleted",
        target_type="backup",
        target_id=str(backup_id),
        ip=request.client.host if request.client else None,
        detail={"file_unlinked": file_unlinked, "file_path": file_path or None},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
