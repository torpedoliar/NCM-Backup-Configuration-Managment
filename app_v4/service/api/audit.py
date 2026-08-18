from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.data.models import User
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, require_role
from app_v4.service.timeutil import to_aware_utc
from sqlalchemy import select

router = APIRouter(tags=["audit"])


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    username: str | None
    action: str
    target_type: str | None
    target_id: str | None
    ip: str | None
    ts: datetime
    detail_json: dict[str, Any] | None

    @field_validator("detail_json", mode="before")
    @classmethod
    def parse_detail_json(cls, value):
        if value is None or isinstance(value, dict):
            return value
        return json.loads(value)


@router.get("/audit", response_model=list[AuditOut])
async def list_audit(
    response: Response,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    from_ts: datetime | None = Query(default=None),
    to_ts: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin")),
) -> list[AuditOut]:
    repo = Repository(session)
    rows = await repo.list_audit(
        limit=limit,
        offset=offset,
        action_prefix=action,
        user_id=user_id,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    total = await repo.count_audit(
        action_prefix=action,
        user_id=user_id,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    response.headers["X-Total-Count"] = str(total)

    user_ids = {row.user_id for row in rows if row.user_id is not None}
    name_map: dict[int, str] = {}
    if user_ids:
        result = await session.execute(select(User.id, User.username).where(User.id.in_(user_ids)))
        name_map = {uid: uname for uid, uname in result.all()}

    out: list[AuditOut] = []
    for row in rows:
        out.append(
            AuditOut(
                id=row.id,
                user_id=row.user_id,
                username=name_map.get(row.user_id) if row.user_id is not None else None,
                action=row.action,
                target_type=row.target_type,
                target_id=row.target_id,
                ip=row.ip,
                ts=to_aware_utc(row.ts),
                detail_json=row.detail_json,
            )
        )
    return out
