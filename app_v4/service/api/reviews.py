from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.review_service import REVIEW_STATUSES, ReviewService
from app_v4.service.timeutil import to_aware_utc

router = APIRouter(tags=["config-reviews"])


class BaselineOut(BaseModel):
    id: int
    kind: str
    switch_id: int | None
    switch_name: str | None = None
    model: str | None
    backup_id: int | None
    content_hash: str
    created_at: datetime


class BaselineCreate(BaseModel):
    kind: str = Field(pattern="^(switch|model)$")
    switch_id: int | None = None
    model: str | None = Field(default=None, max_length=100)
    backup_id: int | None = None


class ReviewOut(BaseModel):
    id: int
    switch_id: int
    switch_name: str | None = None
    backup_id: int
    baseline_id: int | None
    status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    comment: str | None
    diff_summary: dict
    created_at: datetime


class ReviewStatusUpdate(BaseModel):
    status: str = Field(pattern="^(approved|flagged|dismissed)$")
    comment: str | None = Field(default=None, max_length=2000)


def _baseline_out(row, name_by_id: dict[int, str] | None = None) -> BaselineOut:
    return BaselineOut(
        id=row.id,
        kind=row.kind,
        switch_id=row.switch_id,
        switch_name=(name_by_id or {}).get(row.switch_id) if row.switch_id is not None else None,
        model=row.model,
        backup_id=row.backup_id,
        content_hash=row.content_hash,
        created_at=to_aware_utc(row.created_at),
    )


async def _switch_name(session: AsyncSession, switch_id: int) -> str | None:
    repo = Repository(session)
    sw = await repo.get_switch(switch_id)
    return sw.name if sw is not None else None


@router.get("/baselines", response_model=list[BaselineOut])
async def list_baselines(
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
) -> list[BaselineOut]:
    repo = Repository(session)
    rows = await repo.list_baselines()
    name_by_id: dict[int, str] = {}
    for row in rows:
        if row.switch_id is not None and row.switch_id not in name_by_id:
            sw = await repo.get_switch(row.switch_id)
            if sw is not None:
                name_by_id[row.switch_id] = sw.name
    return [_baseline_out(row, name_by_id) for row in rows]


@router.post("/baselines", response_model=BaselineOut, status_code=status.HTTP_201_CREATED)
async def create_baseline(
    payload: BaselineCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    runtime=Depends(get_runtime),
    actor=Depends(require_role("admin")),
) -> BaselineOut:
    repo = Repository(session)
    content_hash = ""
    if payload.kind == "switch":
        if payload.switch_id is None:
            raise problem(422, "Unprocessable Entity", "switch_id is required for switch baseline")
        if await repo.get_switch(payload.switch_id) is None:
            raise problem(422, "Unprocessable Entity", "Referenced switch does not exist")
        existing = await repo.get_baseline_for_switch(await repo.get_switch(payload.switch_id))
        if existing is not None:
            raise problem(409, "Conflict", f"Switch already has a {'model template' if existing.kind == 'model' else 'baseline'}")
    else:
        if not payload.model:
            raise problem(422, "Unprocessable Entity", "model is required for model template")
        # One model template per model value (app-level guard; SQLite unique ignores NULLs).
        existing = None
        for row in await repo.list_baselines():
            if row.kind == "model" and row.model == payload.model:
                existing = row
                break
        if existing is not None:
            raise problem(409, "Conflict", "A template for this model already exists")

    if payload.backup_id is not None:
        backup = await repo.get_backup(payload.backup_id)
        if backup is None:
            raise problem(422, "Unprocessable Entity", "Referenced backup does not exist")
        content_hash = backup.content_hash

    baseline = await repo.create_baseline(
        kind=payload.kind,
        switch_id=payload.switch_id,
        model=payload.model,
        backup_id=payload.backup_id,
        content_hash=content_hash,
        created_by=actor.user_id,
    )
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="baseline.created",
        target_type="baseline",
        target_id=str(baseline.id),
        ip=request.client.host if request.client else None,
        detail={"kind": payload.kind, "switch_id": payload.switch_id, "model": payload.model},
    )
    fresh = await repo.get_baseline(baseline.id)
    return _baseline_out(fresh)


@router.delete("/baselines/{baseline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_baseline(
    baseline_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    runtime=Depends(get_runtime),
    actor=Depends(require_role("admin")),
) -> Response:
    repo = Repository(session)
    deleted = await repo.delete_baseline(baseline_id)
    if not deleted:
        raise problem(404, "Not Found", "Baseline not found")
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="baseline.deleted",
        target_type="baseline",
        target_id=str(baseline_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reviews", response_model=list[ReviewOut])
async def list_reviews(
    status_filter: str | None = Query(default=None, alias="status"),
    switch_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
) -> list[ReviewOut]:
    if status_filter is not None and status_filter not in REVIEW_STATUSES:
        raise problem(422, "Unprocessable Entity", f"invalid status: {status_filter}")
    repo = Repository(session)
    rows = await repo.list_reviews(status=status_filter, switch_id=switch_id, limit=limit, offset=offset)
    out: list[ReviewOut] = []
    for row in rows:
        name = await _switch_name(session, row.switch_id)
        import json

        try:
            summary = json.loads(row.diff_summary or "{}")
        except ValueError:
            summary = {}
        out.append(
            ReviewOut(
                id=row.id,
                switch_id=row.switch_id,
                switch_name=name,
                backup_id=row.backup_id,
                baseline_id=row.baseline_id,
                status=row.status,
                reviewed_by=row.reviewed_by,
                reviewed_at=to_aware_utc(row.reviewed_at),
                comment=row.comment,
                diff_summary=summary,
                created_at=to_aware_utc(row.created_at),
            )
        )
    return out


@router.get("/reviews/{review_id}/diff")
async def review_diff(
    review_id: int,
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
) -> Response:
    repo = Repository(session)
    review = await repo.get_review(review_id)
    if review is None:
        raise problem(404, "Not Found", "Review not found")
    return Response(review.raw_diff, media_type="text/plain; charset=utf-8")


@router.post("/reviews/{review_id}/status", response_model=ReviewOut)
async def update_review_status(
    review_id: int,
    payload: ReviewStatusUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    runtime=Depends(get_runtime),
    actor=Depends(require_role("admin", "operator")),
) -> ReviewOut:
    repo = Repository(session)
    review = await repo.get_review(review_id)
    if review is None:
        raise problem(404, "Not Found", "Review not found")
    review = await repo.update_review(
        review_id,
        status=payload.status,
        reviewed_by=actor.user_id,
        comment=payload.comment,
    )
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action=f"review.{payload.status}",
        target_type="review",
        target_id=str(review_id),
        ip=request.client.host if request.client else None,
        detail={"comment": payload.comment},
    )
    name = await _switch_name(session, review.switch_id)
    import json

    try:
        summary = json.loads(review.diff_summary or "{}")
    except ValueError:
        summary = {}
    return ReviewOut(
        id=review.id,
        switch_id=review.switch_id,
        switch_name=name,
        backup_id=review.backup_id,
        baseline_id=review.baseline_id,
        status=review.status,
        reviewed_by=review.reviewed_by,
        reviewed_at=to_aware_utc(review.reviewed_at),
        comment=review.comment,
        diff_summary=summary,
        created_at=to_aware_utc(review.created_at),
    )


@router.get("/reviews/compliance")
async def reviews_compliance(
    session: AsyncSession = Depends(get_db),
    runtime=Depends(get_runtime),
    _user=Depends(require_role("admin", "operator")),
) -> dict:
    if runtime.review_service is None:
        raise problem(503, "Service Unavailable", "Review service is not initialized")
    return await runtime.review_service.compliance_summary()


@router.get("/reviews/compliance/report")
async def compliance_report(
    format: str = Query("pdf", pattern="^(csv|xlsx|pdf)$"),
    session: AsyncSession = Depends(get_db),
    runtime=Depends(get_runtime),
    _user=Depends(require_role("admin", "operator")),
) -> Response:
    """Export the per-switch compliance table as CSV/XLSX/PDF (ISO evidence)."""
    if runtime.review_service is None:
        raise problem(503, "Service Unavailable", "Review service is not initialized")
    from app_v4.service.reporting import (
        ComplianceRow,
        render_compliance_csv,
        render_compliance_pdf,
        render_compliance_xlsx,
    )

    data = await runtime.review_service.compliance_rows()
    rows = [
        ComplianceRow(
            switch=item["switch"],
            ip=item["ip"],
            model=item["model"],
            baseline=item["baseline"],
            last_backup=item["last_backup"],
            open_reviews=item["open_reviews"],
            last_review=item["last_review"],
            review_state=item["review_state"],
        )
        for item in data
    ]
    stamp = to_aware_utc(datetime.now()).strftime("%Y%m%dT%H%M%SZ")
    if format == "csv":
        body = render_compliance_csv(rows)
        media = "text/csv; charset=utf-8"
    elif format == "xlsx":
        body = render_compliance_xlsx(rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        body = render_compliance_pdf(rows)
        media = "application/pdf"
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="compliance-{stamp}.{format}"'},
    )
