from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.core.password_policy import PasswordPolicy, validate_password
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime
from app_v4.service.timeutil import to_aware_utc

router = APIRouter(prefix="/users", tags=["users"])


def _policy_from_runtime(runtime: ServiceRuntime) -> PasswordPolicy:
    cfg = runtime.auth_settings_provider()
    return PasswordPolicy(
        min_length=cfg.password_min_length,
        require_upper=cfg.password_require_upper,
        require_lower=cfg.password_require_lower,
        require_digit=cfg.password_require_digit,
        require_symbol=cfg.password_require_symbol,
    )


def _validate_or_raise(password: str, runtime: ServiceRuntime) -> None:
    error = validate_password(password, _policy_from_runtime(runtime))
    if error:
        raise problem(422, "Unprocessable Entity", error)


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


class PasswordResetRequest(BaseModel):
    password: str


def _to_out(user) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=to_aware_utc(user.created_at),
        last_login_at=to_aware_utc(user.last_login_at),
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
    _validate_or_raise(payload.password, runtime)
    password_hash = runtime.auth_service.hash_password(payload.password)
    user = await repo.create_user(payload.username, password_hash, payload.role)
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="user.created",
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
        action="user.updated",
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
    if actor.user_id == user_id:
        raise problem(409, "Conflict", "Cannot delete yourself")
    repo = Repository(session)
    deleted = await repo.delete_user(user_id)
    if not deleted:
        raise problem(404, "Not Found", "User not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="user.deleted",
        target_type="user",
        target_id=str(user_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> Response:
    _validate_or_raise(payload.password, runtime)
    repo = Repository(session)
    user = await repo.get_user_by_id(user_id)
    if user is None:
        raise problem(404, "Not Found", "User not found")
    user.password_hash = runtime.auth_service.hash_password(payload.password)
    await session.commit()
    await runtime.audit_writer.record(
        action="user.password_reset_by_admin",
        user_id=actor.user_id,
        target_type="user",
        target_id=str(user_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/unlock", status_code=status.HTTP_204_NO_CONTENT)
async def unlock_user(
    user_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> Response:
    repo = Repository(session)
    user = await repo.get_user_by_id(user_id)
    if user is None:
        raise problem(404, "Not Found", "User not found")
    user.failed_login_count = 0
    user.last_failed_login_at = None
    user.locked_until = None
    await session.commit()
    await runtime.audit_writer.record(
        action="user.unlock_by_admin",
        user_id=actor.user_id,
        target_type="user",
        target_id=str(user_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
