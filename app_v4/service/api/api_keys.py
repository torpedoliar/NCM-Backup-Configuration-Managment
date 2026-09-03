from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.models import ApiKey
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    prefix: str
    key: str


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked: bool


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> ApiKeyCreated:
    repo = Repository(session)
    if await repo.get_api_key_by_name(payload.name) is not None:
        raise problem(409, "Conflict", "API key name already exists")
    plaintext = "ncr_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    prefix = plaintext[:8]
    key = await repo.create_api_key(name=payload.name, key_hash=key_hash, prefix=prefix)
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="apikey.created",
        target_type="api_key",
        target_id=str(key.id),
        ip=request.client.host if request.client else None,
        detail={"name": key.name},
    )
    return ApiKeyCreated(id=key.id, name=key.name, prefix=prefix, key=plaintext)


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    session: AsyncSession = Depends(get_db),
    _actor: AccessClaims = Depends(require_role("admin")),
) -> list[ApiKeyOut]:
    repo = Repository(session)
    return [
        ApiKeyOut(
            id=key.id,
            name=key.name,
            prefix=key.prefix,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            revoked=key.revoked,
        )
        for key in await repo.list_api_keys()
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    request: Request,
    permanent: bool = Query(default=False),
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> Response:
    """Revoke (default) or permanently delete an API key.

    Revoke keeps the row for audit history; permanent removes the row entirely.
    """
    repo = Repository(session)
    key = await session.get(ApiKey, key_id)
    if key is None:
        raise problem(404, "Not Found", "API key not found")
    if permanent:
        await repo.delete_api_key(key_id)
        action = "apikey.deleted"
    else:
        await repo.revoke_api_key(key_id)
        action = "apikey.revoked"
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action=action,
        target_type="api_key",
        target_id=str(key_id),
        ip=request.client.host if request.client else None,
        detail={"name": key.name},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
