from __future__ import annotations

from datetime import datetime

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
    user_id: int
    username: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    repo = Repository(session)
    user = await repo.get_user_by_username(payload.username)
    if user is None or not user.is_active:
        raise problem(401, "Unauthorized", "Invalid username or password")
    if not runtime.auth_service.verify_password(payload.password, user.password_hash):
        raise problem(401, "Unauthorized", "Invalid username or password")

    tokens: TokenPair = runtime.auth_service.issue_token_pair(user.id, user.username, user.role)
    await repo.create_session(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(tokens.refresh_token),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        days_valid=runtime.settings.jwt_refresh_days,
    )
    await repo.mark_user_login(user.id)
    await session.commit()
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
        raise problem(401, "Unauthorized", "Invalid refresh token")
    user = await repo.get_user_by_id(current.user_id)
    if user is None or not user.is_active:
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
    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    session: AsyncSession = Depends(get_db),
) -> Response:
    repo = Repository(session)
    current = await repo.get_session_by_refresh_hash(hash_refresh_token(payload.refresh_token))
    if current is not None:
        await repo.revoke_session(current.id)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(user: AccessClaims = Depends(require_user)) -> MeResponse:
    return MeResponse(user_id=user.user_id, username=user.username, role=user.role)
