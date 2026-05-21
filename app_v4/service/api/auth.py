from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims, TokenPair
from app_v4.data.repository import Repository, hash_refresh_token
from app_v4.service.deps import get_db, get_runtime, require_user
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    repo = Repository(session)
    user = await repo.get_user_by_username(payload.username)
    ip = request.client.host if request.client else None
    if user is None or not user.is_active:
        await runtime.audit_writer.record(
            action="auth.login_failed",
            ip=ip,
            detail={"username": payload.username},
        )
        raise problem(401, "Unauthorized", "Invalid username or password")

    auth_cfg = runtime.auth_settings_provider()
    now = datetime.utcnow()

    if user.locked_until is not None and user.locked_until > now:
        await runtime.audit_writer.record(
            action="auth.login_blocked_locked",
            user_id=user.id,
            ip=ip,
            detail={"username": payload.username},
        )
        raise problem(423, "Locked", "Account temporarily locked")

    if not runtime.auth_service.verify_password(payload.password, user.password_hash):
        if (
            user.last_failed_login_at is None
            or (now - user.last_failed_login_at) > timedelta(minutes=auth_cfg.lockout_window_minutes)
        ):
            user.failed_login_count = 1
        else:
            user.failed_login_count = (user.failed_login_count or 0) + 1
        user.last_failed_login_at = now
        if (
            auth_cfg.lockout_threshold > 0
            and user.failed_login_count >= auth_cfg.lockout_threshold
        ):
            user.locked_until = now + timedelta(minutes=auth_cfg.lockout_duration_minutes)
            await runtime.audit_writer.record(
                action="auth.locked",
                user_id=user.id,
                ip=ip,
                detail={"username": user.username},
            )
        await session.commit()
        await runtime.audit_writer.record(
            action="auth.login_failed",
            user_id=user.id,
            ip=ip,
            detail={"username": payload.username},
        )
        raise problem(401, "Unauthorized", "Invalid username or password")

    user.failed_login_count = 0
    user.last_failed_login_at = None
    user.locked_until = None

    tokens: TokenPair = runtime.auth_service.issue_token_pair(user.id, user.username, user.role)
    await repo.create_session(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(tokens.refresh_token),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        days_valid=runtime.settings.jwt_refresh_days,
    )
    await repo.mark_user_login(user.id)
    await session.commit()
    await runtime.audit_writer.record(
        action="auth.login_success",
        user_id=user.id,
        ip=ip,
        detail={"username": user.username},
    )
    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    repo = Repository(session)
    current = await repo.get_session_by_refresh_hash(hash_refresh_token(payload.refresh_token))
    if current is None or current.revoked or current.expires_at <= datetime.utcnow():
        await runtime.audit_writer.record(
            action="auth.refresh_failed",
            ip=request.client.host if request.client else None,
        )
        raise problem(401, "Unauthorized", "Invalid refresh token")
    user = await repo.get_user_by_id(current.user_id)
    if user is None or not user.is_active:
        await runtime.audit_writer.record(
            action="auth.refresh_failed",
            user_id=current.user_id,
            ip=request.client.host if request.client else None,
        )
        raise problem(401, "Unauthorized", "Invalid refresh token")

    await repo.revoke_session(current.id)
    tokens: TokenPair = runtime.auth_service.issue_token_pair(user.id, user.username, user.role)
    await repo.create_session(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(tokens.refresh_token),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        days_valid=runtime.settings.jwt_refresh_days,
    )
    await session.commit()
    await runtime.audit_writer.record(
        action="auth.refresh",
        user_id=user.id,
        ip=request.client.host if request.client else None,
    )
    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
) -> Response:
    repo = Repository(session)
    current = await repo.get_session_by_refresh_hash(hash_refresh_token(payload.refresh_token))
    if current is not None:
        await repo.revoke_session(current.id)
        await session.commit()
        await runtime.audit_writer.record(
            action="auth.logout",
            user_id=current.user_id,
            ip=request.client.host if request.client else None,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(
    user: AccessClaims = Depends(require_user),
    session: AsyncSession = Depends(get_db),
) -> MeResponse:
    repo = Repository(session)
    db_user = await repo.get_user_by_id(user.user_id)
    if db_user is None:
        raise problem(401, "Unauthorized", "User not found")
    return MeResponse(
        id=db_user.id,
        username=db_user.username,
        role=db_user.role,
        is_active=db_user.is_active,
    )
