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

router = APIRouter(prefix="/credentials", tags=["credentials"])


class CredentialOut(BaseModel):
    id: int
    name: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _credential_to_out(cred) -> CredentialOut:
    return CredentialOut(
        id=cred.id,
        name=cred.name,
        created_at=getattr(cred, "created_at", None),
        updated_at=getattr(cred, "updated_at", None),
    )


class CredentialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    enable_password: str = Field(default="", max_length=256)


class CredentialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    username: str | None = Field(default=None, min_length=1, max_length=128)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    enable_password: str | None = Field(default=None, max_length=256)


def _require_crypto(runtime: ServiceRuntime):
    if runtime.crypto_service is None:
        raise problem(503, "Service Unavailable", "CryptoService is not initialized")
    return runtime.crypto_service


@router.get("", response_model=list[CredentialOut])
async def list_credentials(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator")),
) -> list[CredentialOut]:
    repo = Repository(session)
    return [_credential_to_out(c) for c in await repo.list_credentials()]


@router.post("", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
async def create_credential(
    payload: CredentialCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> CredentialOut:
    crypto = _require_crypto(runtime)
    repo = Repository(session)
    if await repo.get_credential_by_name(payload.name) is not None:
        raise problem(409, "Conflict", "Credential name already exists")
    enc_blob = crypto.encrypt_credential(payload.username, payload.password, payload.enable_password)
    cred = await repo.create_credential(name=payload.name, enc_blob=enc_blob)
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="credential.create",
        target_type="credential",
        target_id=str(cred.id),
        ip=request.client.host if request.client else None,
        detail={"name": cred.name},
    )
    return _credential_to_out(cred)


@router.patch("/{cred_id}", response_model=CredentialOut)
async def update_credential(
    cred_id: int,
    payload: CredentialUpdate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> CredentialOut:
    crypto = _require_crypto(runtime)
    repo = Repository(session)
    existing = await repo.get_credential(cred_id)
    if existing is None:
        raise problem(404, "Not Found", "Credential not found")

    secret_changed = (
        payload.username is not None
        or payload.password is not None
        or payload.enable_password is not None
    )
    new_blob = existing.enc_blob
    if secret_changed:
        decrypted = crypto.decrypt_credential(existing.enc_blob)
        new_blob = crypto.encrypt_credential(
            username=payload.username if payload.username is not None else decrypted["username"],
            password=payload.password if payload.password is not None else decrypted["password"],
            enable_password=(
                payload.enable_password
                if payload.enable_password is not None
                else decrypted["enable_password"]
            ),
        )

    updated = await repo.update_credential(cred_id, name=payload.name, enc_blob=new_blob)
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="credential.update",
        target_type="credential",
        target_id=str(cred_id),
        ip=request.client.host if request.client else None,
        detail={
            "name_changed": payload.name is not None,
            "secret_changed": secret_changed,
        },
    )
    return _credential_to_out(updated)


@router.delete("/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    cred_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> Response:
    repo = Repository(session)
    try:
        deleted = await repo.delete_credential(cred_id)
    except ValueError:
        raise problem(409, "Conflict", "Credential is in use by switches")
    if not deleted:
        raise problem(404, "Not Found", "Credential not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="credential.delete",
        target_type="credential",
        target_id=str(cred_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
