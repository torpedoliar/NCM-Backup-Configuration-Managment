from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern="^(admin|operator|viewer)$")


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|operator|viewer)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


def _to_out(user) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("", response_model=list[UserOut])
async def list_users(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin")),
) -> list[UserOut]:
    repo = Repository(session)
    users = await repo.list_users()
    return [_to_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> UserOut:
    repo = Repository(session)
    if await repo.get_user_by_username(payload.username) is not None:
        raise problem(409, "Conflict", "Username already exists")
    password_hash = runtime.auth_service.hash_password(payload.password)
    user = await repo.create_user(payload.username, password_hash, payload.role)
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="user.create",
        target_type="user",
        target_id=str(user.id),
        ip=request.client.host if request.client else None,
        detail={"username": user.username, "role": user.role},
    )
    return _to_out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> UserOut:
    repo = Repository(session)
    password_hash = (
        runtime.auth_service.hash_password(payload.password) if payload.password else None
    )
    user = await repo.update_user(
        user_id,
        role=payload.role,
        is_active=payload.is_active,
        password_hash=password_hash,
    )
    if user is None:
        raise problem(404, "Not Found", "User not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="user.update",
        target_type="user",
        target_id=str(user.id),
        ip=request.client.host if request.client else None,
        detail={
            "role": payload.role,
            "is_active": payload.is_active,
            "password_changed": payload.password is not None,
        },
    )
    return _to_out(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> Response:
    repo = Repository(session)
    deleted = await repo.delete_user(user_id)
    if not deleted:
        raise problem(404, "Not Found", "User not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="user.delete",
        target_type="user",
        target_id=str(user_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
