from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.utcdatetime import utc_now
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
    started_by: int | None = None
    started_at: datetime | None = None
    comment: str | None
    diff_summary: dict
    created_at: datetime
    notes: list["ReviewNoteOut"] = []


class ReviewNoteOut(BaseModel):
    id: int
    author_id: int | None
    author_name: str | None = None
    body: str
    created_at: datetime


class ReviewNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


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

    # Resolve the golden-config source. When no backup is picked, fall back to
    # the latest successful backup of that switch (or, for model templates, of
    # any switch with that model). A baseline with no source is a zombie: the
    # drift review pipeline silently skips it, so we refuse to create one.
    if payload.backup_id is None:
        source_backup = (
            await repo.get_latest_backup(payload.switch_id)
            if payload.kind == "switch"
            else await repo.get_latest_backup_for_model(payload.model)
        )
        if source_backup is None:
            raise problem(
                422,
                "Unprocessable Entity",
                "No successful backup found to snapshot as the golden config. Run a backup first.",
            )
        payload.backup_id = source_backup.id
    backup = await repo.get_backup(payload.backup_id)
    if backup is None:
        raise problem(422, "Unprocessable Entity", "Referenced backup does not exist")
    if not backup.success:
        raise problem(422, "Unprocessable Entity", "Referenced backup was not successful")
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


@router.post("/baselines/{baseline_id}/refresh")
async def refresh_baseline(
    baseline_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    runtime=Depends(get_runtime),
    actor=Depends(require_role("admin")),
) -> dict:
    """On-demand review of the latest backup against the baseline (re-attestation).

    Reads the old golden config and the latest successful backup from disk,
    compares them, and when they drift opens a pending review BEFORE re-pointing
    the baseline at the new config. The baseline cycle clock always resets. The
    outcome (drift + review id, or no drift) is recorded in the audit log.
    """
    repo = Repository(session)
    baseline = await repo.get_baseline(baseline_id)
    if baseline is None:
        raise problem(404, "Not Found", "Baseline not found")
    target = (
        await repo.get_latest_backup(baseline.switch_id)
        if baseline.kind == "switch"
        else await repo.get_latest_backup_for_model(baseline.model)
    )
    if target is None:
        raise problem(422, "Unprocessable Entity", "No successful backup available to review")

    # Compare the stored golden vs the latest backup (both from disk).
    old_golden = await repo.get_backup(baseline.backup_id) if baseline.backup_id else None
    golden_text = None
    if old_golden is not None and old_golden.file_path:
        path = Path(old_golden.file_path)
        if path.exists():
            golden_text = path.read_text(encoding="utf-8")
    target_text = None
    if target.file_path:
        path = Path(target.file_path)
        if path.exists():
            target_text = path.read_text(encoding="utf-8")

    drifted = False
    review_id: int | None = None
    review_switch = await repo.get_switch(
        baseline.switch_id if baseline.kind == "switch" else target.switch_id
    )
    if (
        runtime.review_service is not None
        and golden_text is not None
        and target_text is not None
        and review_switch is not None
        and target.id != baseline.backup_id
    ):
        outcome = await runtime.review_service.on_backup_complete(
            switch=review_switch,
            backup_id=target.id,
            content_text=target_text,
            baseline_text=golden_text,
            baseline_id=baseline.id,
        )
        drifted = outcome.drifted
        review_id = outcome.review_id

    # Re-point and reset the cycle clock regardless of drift.
    baseline.backup_id = target.id
    baseline.content_hash = target.content_hash
    baseline.created_at = utc_now()
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="baseline.refreshed",
        target_type="baseline",
        target_id=str(baseline_id),
        ip=request.client.host if request.client else None,
        detail={
            "backup_id": target.id,
            "drifted": drifted,
            "review_id": review_id,
        },
    )
    fresh = await repo.get_baseline(baseline_id)
    name_by_id: dict[int, str] = {}
    if fresh is not None and fresh.switch_id is not None:
        sw_name = await _switch_name(session, fresh.switch_id)
        if sw_name is not None:
            name_by_id[fresh.switch_id] = sw_name
    return {
        "baseline": _baseline_out(fresh, name_by_id).model_dump(),
        "drifted": drifted,
        "review_id": review_id,
    }


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


async def _review_out(session: AsyncSession, row, include_notes: bool = False) -> ReviewOut:
    """Shared ReviewOut builder (switch name, summary, optional notes thread)."""
    import json

    repo = Repository(session)
    name = await _switch_name(session, row.switch_id)
    try:
        summary = json.loads(row.diff_summary or "{}")
    except ValueError:
        summary = {}
    notes: list[ReviewNoteOut] = []
    if include_notes:
        author_names: dict[int, str] = {}
        for note in await repo.list_review_notes(row.id):
            if note.author_id is not None and note.author_id not in author_names:
                author = await repo.get_user_by_id(note.author_id)
                author_names[note.author_id] = author.username if author else f"user-{note.author_id}"
            notes.append(
                ReviewNoteOut(
                    id=note.id,
                    author_id=note.author_id,
                    author_name=author_names.get(note.author_id),
                    body=note.body,
                    created_at=to_aware_utc(note.created_at),
                )
            )
    return ReviewOut(
        id=row.id,
        switch_id=row.switch_id,
        switch_name=name,
        backup_id=row.backup_id,
        baseline_id=row.baseline_id,
        status=row.status,
        reviewed_by=row.reviewed_by,
        reviewed_at=to_aware_utc(row.reviewed_at),
        started_by=row.started_by,
        started_at=to_aware_utc(row.started_at),
        comment=row.comment,
        diff_summary=summary,
        created_at=to_aware_utc(row.created_at),
        notes=notes,
    )


@router.get("/reviews", response_model=list[ReviewOut])
async def list_reviews(
    status_filter: str | None = Query(default=None, alias="status"),
    switch_id: int | None = None,
    include_notes: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
) -> list[ReviewOut]:
    if status_filter is not None and status_filter not in REVIEW_STATUSES:
        raise problem(422, "Unprocessable Entity", f"invalid status: {status_filter}")
    repo = Repository(session)
    rows = await repo.list_reviews(status=status_filter, switch_id=switch_id, limit=limit, offset=offset)
    return [await _review_out(session, row, include_notes=include_notes) for row in rows]


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


@router.post("/reviews/{review_id}/start", response_model=ReviewOut)
async def start_review(
    review_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    runtime=Depends(get_runtime),
    actor=Depends(require_role("admin", "operator")),
) -> ReviewOut:
    """Claim a pending review: status -> in_review with reviewer + timestamp."""
    repo = Repository(session)
    review = await repo.get_review(review_id)
    if review is None:
        raise problem(404, "Not Found", "Review not found")
    if review.status != "pending":
        raise problem(409, "Conflict", f"Review is already {review.status}")
    review = await repo.update_review(
        review_id, status="in_review", started_by=actor.user_id, started_at=utc_now()
    )
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="review.started",
        target_type="review",
        target_id=str(review_id),
        ip=request.client.host if request.client else None,
    )
    return await _review_out(session, review, include_notes=True)


@router.get("/reviews/{review_id}/notes", response_model=list[ReviewNoteOut])
async def list_review_notes(
    review_id: int,
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
) -> list[ReviewNoteOut]:
    repo = Repository(session)
    review = await repo.get_review(review_id)
    if review is None:
        raise problem(404, "Not Found", "Review not found")
    review_out = await _review_out(session, review, include_notes=True)
    return review_out.notes


@router.post("/reviews/{review_id}/notes", response_model=list[ReviewNoteOut])
async def add_review_note(
    review_id: int,
    payload: ReviewNoteCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    runtime=Depends(get_runtime),
    actor=Depends(require_role("admin", "operator")),
) -> list[ReviewNoteOut]:
    """Append a note to the review's decision thread (append-only audit trail)."""
    repo = Repository(session)
    review = await repo.get_review(review_id)
    if review is None:
        raise problem(404, "Not Found", "Review not found")
    await repo.create_review_note(review_id, actor.user_id, payload.body.strip())
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="review.note_added",
        target_type="review",
        target_id=str(review_id),
        ip=request.client.host if request.client else None,
    )
    review_out = await _review_out(session, review, include_notes=True)
    return review_out.notes


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
    # Best-effort decision email (approved/flagged/dismissed); never breaks the API.
    try:
        from app_v4.core.runtime_settings import load_runtime_settings
        from app_v4.core.paths import resolve_paths
        from app_v4.service import email_events

        paths = resolve_paths(runtime.settings)
        cfg = load_runtime_settings(paths.data_dir / "runtime_settings.json").notify
        if runtime.notify is not None and cfg.enabled and cfg.email_enabled and cfg.email_review_events:
            reviewer_name = f"user-{actor.user_id}"
            if getattr(actor, "username", None):
                reviewer_name = actor.username
            sw = await repo.get_switch(review.switch_id)
            content = email_events.review_decision_email(
                sw.name if sw else f"#{review.switch_id}",
                review.id,
                payload.status,
                payload.comment,
                reviewer_name,
                f"{cfg.app_public_url.rstrip('/')}/config-review",
            )
            await runtime.notify.email(
                content["subject"], content["body_text"], body_html=content["body_html"]
            )
    except Exception:  # noqa: BLE001 - email must never break the decision flow
        import logging

        logging.getLogger(__name__).warning("review decision email failed", exc_info=True)
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action=f"review.{payload.status}",
        target_type="review",
        target_id=str(review_id),
        ip=request.client.host if request.client else None,
        detail={"comment": payload.comment},
    )
    return await _review_out(session, review, include_notes=True)


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
            next_review=item.get("next_review", ""),
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
