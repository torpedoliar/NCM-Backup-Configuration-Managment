from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims, TokenError
from app_v4.data.repository import Repository
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

bearer = HTTPBearer(auto_error=False)


def get_runtime(request: Request) -> ServiceRuntime:
    return request.app.state.runtime


async def get_db(runtime: ServiceRuntime = Depends(get_runtime)) -> AsyncIterator[AsyncSession]:
    async with runtime.session_factory() as session:
        yield session


async def _lookup_api_key(
    presented: str | None,
    session: AsyncSession,
) -> tuple[str, list[str]] | None:
    """Validated (name, scopes) for a presented key, or None when unknown/revoked."""
    if not presented:
        return None
    key_hash = hashlib.sha256(presented.encode("utf-8")).hexdigest()
    repo = Repository(session)
    key = await repo.get_api_key_by_hash(key_hash)
    if key is None:
        return None
    await repo.touch_api_key_last_used(key.id)
    await session.commit()
    return key.name, Repository.get_api_key_scopes(key)


async def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> str:
    presented = x_api_key.strip() if x_api_key else None
    if presented is None and authorization:
        scheme, separator, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and separator:
            presented = value.strip()
    if not presented:
        raise problem(401, "Unauthorized", "Missing API key")

    found = await _lookup_api_key(presented, session)
    if found is None:
        raise problem(401, "Unauthorized", "Invalid or revoked API key")
    return found[0]


def require_scoped_key(*scopes: str):
    """API-key-only dependency: key must carry at least one of `scopes`.

    Legacy keys (no scopes) get 403 here — all read endpoints use the
    combined `require_key_or_jwt` variant instead.
    """

    async def dependency(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        session: AsyncSession = Depends(get_db),
    ) -> str:
        presented = x_api_key.strip() if x_api_key else None
        if presented is None and authorization:
            scheme, separator, value = authorization.partition(" ")
            if scheme.lower() == "bearer" and separator:
                presented = value.strip()
        if not presented:
            raise problem(401, "Unauthorized", "Missing API key")

        found = await _lookup_api_key(presented, session)
        if found is None:
            raise problem(401, "Unauthorized", "Invalid or revoked API key")
        name, key_scopes = found
        if not set(key_scopes) & set(scopes):
            raise problem(403, "Forbidden", "API key lacks required scope")
        return name

    return dependency


def require_key_or_jwt(*scopes: str):
    """Combined dependency: valid JWT (any authenticated role) OR scoped API key.

    Replaces `require_role(...)` on endpoints opened to DataGuard.
    No credential at all -> 401; credential present but insufficient -> 403.
    JWT identity returns the full AccessClaims (role checks preserved for
    mixed endpoints); key identity returns "key:<name>".
    """

    async def dependency(
        request: Request,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        session: AsyncSession = Depends(get_db),
    ) -> AccessClaims | str:
        runtime: ServiceRuntime = request.app.state.runtime
        presented = x_api_key.strip() if x_api_key else None
        bearer_value: str | None = None
        if authorization:
            scheme, separator, value = authorization.partition(" ")
            if scheme.lower() == "bearer" and separator and value.strip():
                bearer_value = value.strip()
        # JWT path first: return live claims so role checks keep working.
        if bearer_value is not None and presented is None:
            try:
                return runtime.auth_service.verify_access_token(bearer_value)
            except TokenError:
                raise problem(401, "Unauthorized", "Invalid bearer token")
        if presented is not None:
            found = await _lookup_api_key(presented, session)
            if found is None:
                raise problem(401, "Unauthorized", "Invalid or revoked API key")
            name, key_scopes = found
            if not set(key_scopes) & set(scopes):
                raise problem(403, "Forbidden", "API key lacks required scope")
            return f"key:{name}"
        raise problem(401, "Unauthorized", "Missing credentials")

    return dependency


def require_role_or_key(*allowed_roles: str, scope: str):
    """Combined dependency preserving JWT role checks: JWT callers must hold one
    of `allowed_roles`; API-key callers must carry `scope`. Returns AccessClaims
    for JWT, "key:<name>" for keys. 401/403 semantics match require_key_or_jwt.
    """

    role_dep = require_role(*allowed_roles)
    key_dep = require_key_or_jwt(scope)

    async def dependency(
        request: Request,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        session: AsyncSession = Depends(get_db),
    ) -> AccessClaims | str:
        presented = x_api_key.strip() if x_api_key else None
        if presented is not None:
            # key_dep is a FastAPI dependency factory: calling it returns the
            # inner async dependency; invoke it with the already-resolved values.
            inner = key_dep(
                request=request, authorization=authorization, x_api_key=x_api_key, session=session
            )
            result = inner() if callable(inner) else inner
            return await result if asyncio.iscoroutine(result) else result
        creds = (
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=authorization.partition(" ")[2].strip())
            if authorization and authorization.partition(" ")[0].lower() == "bearer"
            else None
        )
        # require_user / require_role are sync when called directly (FastAPI
        # Depends wrappers are only async under the framework): call plainly.
        # require_role returns the inner `dependency` closure; invoking it with
        # the user returns the checked claims (or raises 401/403).
        user = require_user(credentials=creds, runtime=request.app.state.runtime)
        return role_dep(user=user)

    return dependency


def audit_identity(auth: AccessClaims | str) -> tuple[int | None, dict]:
    """(user_id, extra_detail) for audit_writer from a `require_key_or_jwt` identity.

    JWT path (AccessClaims) -> real user_id; API-key path ("key:<name>") ->
    user_id None (column is nullable) plus {"key": name} in the audit detail.
    Never includes secrets.
    """
    if isinstance(auth, AccessClaims):
        return auth.user_id, {}
    if isinstance(auth, str) and auth.startswith("key:"):
        return None, {"key": auth[4:]}
    return None, {}


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
