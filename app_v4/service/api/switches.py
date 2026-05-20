from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/switches", tags=["switches"])

VALID_PROTOCOLS = {"ssh", "telnet", "http", "https", "websmart", "websmart-v2"}


class CredentialRef(BaseModel):
    id: int
    name: str


class SwitchOut(BaseModel):
    id: int
    name: str
    ip: str
    host: str
    protocol: str
    port: int
    notes: str | None
    credential: CredentialRef
    credential_id: int
    is_active: bool


class SwitchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    ip: str = Field(min_length=1, max_length=255)
    protocol: str = Field(min_length=1, max_length=20)
    port: int = Field(ge=1, le=65535)
    credential_id: int
    notes: str | None = None


class SwitchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    ip: str | None = Field(default=None, min_length=1, max_length=255)
    protocol: str | None = Field(default=None, min_length=1, max_length=20)
    port: int | None = Field(default=None, ge=1, le=65535)
    credential_id: int | None = None
    notes: str | None = None


def _to_out(switch) -> SwitchOut:
    return SwitchOut(
        id=switch.id,
        name=switch.name,
        ip=switch.ip,
        host=switch.ip,
        protocol=switch.protocol,
        port=switch.port,
        notes=switch.notes,
        credential=CredentialRef(id=switch.credential.id, name=switch.credential.name),
        credential_id=switch.credential_id,
        is_active=True,
    )


def _validate_protocol(protocol: str) -> None:
    if protocol not in VALID_PROTOCOLS:
        raise problem(
            422,
            "Unprocessable Entity",
            f"Unsupported protocol '{protocol}'. Must be one of {sorted(VALID_PROTOCOLS)}",
        )


@router.get("", response_model=list[SwitchOut])
async def list_switches(
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[SwitchOut]:
    repo = Repository(session)
    return [_to_out(s) for s in await repo.list_switches()]


@router.post("", response_model=SwitchOut, status_code=status.HTTP_201_CREATED)
async def create_switch(
    payload: SwitchCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> SwitchOut:
    _validate_protocol(payload.protocol)
    repo = Repository(session)
    if await repo.get_switch_by_name(payload.name) is not None:
        raise problem(409, "Conflict", "Switch name already exists")
    if await repo.get_credential(payload.credential_id) is None:
        raise problem(422, "Unprocessable Entity", "Referenced credential does not exist")

    switch = await repo.create_switch(
        name=payload.name,
        ip=payload.ip,
        protocol=payload.protocol,
        port=payload.port,
        credential_id=payload.credential_id,
        notes=payload.notes,
    )
    await session.commit()

    fresh = await repo.get_switch(switch.id)

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="switch.create",
        target_type="switch",
        target_id=str(switch.id),
        ip=request.client.host if request.client else None,
        detail={"name": switch.name, "ip": switch.ip, "protocol": switch.protocol},
    )
    return _to_out(fresh)


@router.get("/{switch_id}", response_model=SwitchOut)
async def get_switch(
    switch_id: int,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> SwitchOut:
    repo = Repository(session)
    switch = await repo.get_switch(switch_id)
    if switch is None:
        raise problem(404, "Not Found", "Switch not found")
    return _to_out(switch)


@router.patch("/{switch_id}", response_model=SwitchOut)
async def update_switch(
    switch_id: int,
    payload: SwitchUpdate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin", "operator")),
) -> SwitchOut:
    if payload.protocol is not None:
        _validate_protocol(payload.protocol)
    repo = Repository(session)
    if payload.credential_id is not None and await repo.get_credential(payload.credential_id) is None:
        raise problem(422, "Unprocessable Entity", "Referenced credential does not exist")

    updated = await repo.update_switch(
        switch_id,
        name=payload.name,
        ip=payload.ip,
        protocol=payload.protocol,
        port=payload.port,
        credential_id=payload.credential_id,
        notes=payload.notes,
    )
    if updated is None:
        raise problem(404, "Not Found", "Switch not found")
    await session.commit()
    fresh = await repo.get_switch(switch_id)

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="switch.update",
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
        detail=payload.model_dump(exclude_none=True),
    )
    return _to_out(fresh)


@router.delete("/{switch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_switch(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> Response:
    repo = Repository(session)
    deleted = await repo.delete_switch(switch_id)
    if not deleted:
        raise problem(404, "Not Found", "Switch not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="switch.delete",
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
