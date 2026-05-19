from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, require_role

router = APIRouter(tags=["audit"])


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
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
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin")),
) -> list[AuditOut]:
    repo = Repository(session)
    rows = await repo.list_audit(limit=limit)
    return [AuditOut.model_validate(row) for row in rows]
