from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims, TokenError
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

bearer = HTTPBearer(auto_error=False)


def get_runtime(request: Request) -> ServiceRuntime:
    return request.app.state.runtime


async def get_db(runtime: ServiceRuntime = Depends(get_runtime)) -> AsyncIterator[AsyncSession]:
    async with runtime.session_factory() as session:
        yield session


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    runtime: ServiceRuntime = Depends(get_runtime),
) -> AccessClaims:
    if credentials is None:
        raise problem(401, "Unauthorized", "Missing bearer token")
    try:
        return runtime.auth_service.verify_access_token(credentials.credentials)
    except TokenError:
        raise problem(401, "Unauthorized", "Invalid bearer token")


def require_role(*allowed_roles: str) -> Callable[[AccessClaims], AccessClaims]:
    def dependency(user: AccessClaims = Depends(require_user)) -> AccessClaims:
        if user.role not in allowed_roles:
            raise problem(403, "Forbidden", "User role is not permitted for this operation")
        return user

    return dependency
