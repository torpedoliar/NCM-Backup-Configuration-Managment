from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import audit_identity, get_db, get_runtime, require_key_or_jwt, require_role, require_role_or_key
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
    deactivated_at: datetime | None = None
    model: str | None = None


class SwitchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    ip: str = Field(min_length=1, max_length=255)
    protocol: str = Field(min_length=1, max_length=20)
    port: int = Field(ge=1, le=65535)
    credential_id: int
    notes: str | None = None
    model: str | None = Field(default=None, max_length=100)


class SwitchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    ip: str | None = Field(default=None, min_length=1, max_length=255)
    protocol: str | None = Field(default=None, min_length=1, max_length=20)
    port: int | None = Field(default=None, ge=1, le=65535)
    credential_id: int | None = None
    notes: str | None = None
    model: str | None = Field(default=None, max_length=100)


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
        is_active=switch.is_active,
        deactivated_at=switch.deactivated_at,
        model=switch.model,
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
    include_inactive: bool = False,
    session: AsyncSession = Depends(get_db),
    _auth = Depends(require_key_or_jwt("read")),
) -> list[SwitchOut]:
    repo = Repository(session)
    return [_to_out(s) for s in await repo.list_switches(include_inactive=include_inactive)]


@router.post("", response_model=SwitchOut, status_code=status.HTTP_201_CREATED)
async def create_switch(
    payload: SwitchCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    _auth = Depends(require_role_or_key("admin", "operator", scope="switches:write")),
) -> SwitchOut:
    audit_user_id, audit_extra = audit_identity(_auth)
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
        model=payload.model,
    )
    await session.commit()

    fresh = await repo.get_switch(switch.id)

    await runtime.audit_writer.record(
        user_id=audit_user_id,
        action="switch.created",
        target_type="switch",
        target_id=str(switch.id),
        ip=request.client.host if request.client else None,
        detail={"name": switch.name, "ip": switch.ip, "protocol": switch.protocol, **audit_extra},
    )
    return _to_out(fresh)


@router.get("/{switch_id}", response_model=SwitchOut)
async def get_switch(
    switch_id: int,
    session: AsyncSession = Depends(get_db),
    _auth = Depends(require_key_or_jwt("read")),
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
    _auth = Depends(require_role_or_key("admin", "operator", scope="switches:write")),
) -> SwitchOut:
    audit_user_id, audit_extra = audit_identity(_auth)
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
        model=payload.model,
    )
    if updated is None:
        raise problem(404, "Not Found", "Switch not found")
    await session.commit()
    fresh = await repo.get_switch(switch_id)

    await runtime.audit_writer.record(
        user_id=audit_user_id,
        action="switch.updated",
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
        detail={**payload.model_dump(exclude_none=True), **audit_extra},
    )
    return _to_out(fresh)


@router.post("/{switch_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_switch(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    _auth = Depends(require_role_or_key("admin", "operator", scope="switches:write")),
) -> Response:
    audit_user_id, audit_extra = audit_identity(_auth)
    repo = Repository(session)
    switch = await repo.deactivate_switch(switch_id)
    if switch is None:
        raise problem(404, "Not Found", "Switch not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=audit_user_id,
        action="switch.deactivated",
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
        detail=audit_extra,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{switch_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
async def activate_switch(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    _auth = Depends(require_role_or_key("admin", "operator", scope="switches:write")),
) -> Response:
    audit_user_id, audit_extra = audit_identity(_auth)
    repo = Repository(session)
    switch = await repo.activate_switch(switch_id)
    if switch is None:
        raise problem(404, "Not Found", "Switch not found")
    await session.commit()

    await runtime.audit_writer.record(
        user_id=audit_user_id,
        action="switch.activated",
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
        detail=audit_extra,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{switch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_switch(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    _auth = Depends(require_role_or_key("admin", scope="switches:write")),
) -> Response:
    audit_user_id, audit_extra = audit_identity(_auth)
    repo = Repository(session)
    switch = await repo.get_switch(switch_id)
    if switch is None:
        raise problem(404, "Not Found", "Switch not found")
    if switch.is_active:
        raise problem(409, "Conflict", "Switch must be deactivated before delete")
    await repo.delete_switch(switch_id)
    await session.commit()

    await runtime.audit_writer.record(
        user_id=audit_user_id,
        action="switch.deleted",
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
        detail=audit_extra,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class SyncDataGuardPayload(BaseModel):
    dg_url: str | None = None
    api_key: str | None = None


class SyncDataGuardResponse(BaseModel):
    success: bool
    updated_count: int
    matched_count: int
    devices_total: int
    updated_switches: list[dict[str, str]]
    message: str


@router.post("/sync-dataguard", response_model=SyncDataGuardResponse)
async def sync_switches_from_dataguard(
    payload: SyncDataGuardPayload | None = None,
    request: Request = None,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    _auth = Depends(require_role_or_key("admin", "operator", scope="switches:write")),
) -> SyncDataGuardResponse:
    """Sync switch names and models from DataGuard devices based on matching IP addresses."""
    import httpx
    from app_v4.core.paths import resolve_paths
    from app_v4.core.runtime_settings import load_runtime_settings
    from app_v4.core.utcdatetime import utc_now

    audit_user_id, audit_extra = audit_identity(_auth)
    repo = Repository(session)

    # Determine DG URL
    dg_url = payload.dg_url if payload and payload.dg_url else None
    api_key = payload.api_key if payload and payload.api_key else None

    paths = resolve_paths(runtime.settings)
    rs = load_runtime_settings(paths.data_dir / "runtime_settings.json")

    if not dg_url:
        webhook_url = rs.notify.webhook_url.strip() if rs.notify.webhook_url else ""
        if webhook_url:
            idx = webhook_url.find("/api/ncm")
            dg_url = webhook_url[:idx] if idx != -1 else webhook_url.rstrip("/")

    if not dg_url:
        import os
        dg_url = os.environ.get("DATAGUARD_URL", "").strip() or None

    if not dg_url:
        raise problem(
            422,
            "Unprocessable Entity",
            "URL DataGuard belum diketahui. Atur Webhook NCM di DataGuard Settings atau masukkan URL DataGuard.",
        )

    req_key = request.headers.get("x-api-key") if request else None
    if not api_key and req_key:
        api_key = req_key.strip()

    secret = rs.notify.webhook_secret.strip() if rs.notify.webhook_secret else ""
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    elif secret:
        headers["X-NCM-Secret"] = secret
        headers["X-API-Key"] = secret

    target_url = f"{dg_url.rstrip('/')}/api/ncm/devices"
    try:
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            resp = await client.get(target_url, headers=headers)
            if resp.status_code != 200:
                err_text = resp.text[:200]
                try:
                    err_json = resp.json()
                    err_text = err_json.get("error") or err_json.get("message") or err_text
                except Exception:
                    pass
                raise problem(
                    502,
                    "Bad Gateway",
                    f"DataGuard API ({target_url}) merespons {resp.status_code}: {err_text}",
                )
            data = resp.json()
    except httpx.RequestError as exc:
        raise problem(502, "Bad Gateway", f"Gagal menghubungi DataGuard di {target_url}: {str(exc)}")

    dg_devices = data.get("devices", [])
    if not isinstance(dg_devices, list):
        raise problem(502, "Bad Gateway", "Format data perangkat dari DataGuard tidak valid.")

    ncm_switches = await repo.list_switches(include_inactive=True)
    updated_switches: list[dict[str, str]] = []
    matched_count = 0

    for dev in dg_devices:
        dev_ip = str(dev.get("ip") or "").strip()
        dev_name = str(dev.get("name") or "").strip()
        dev_model = str(dev.get("model") or "").strip()
        if not dev_ip or not dev_name:
            continue

        for sw in ncm_switches:
            if sw.ip.strip() == dev_ip:
                matched_count += 1
                name_changed = sw.name != dev_name
                model_changed = bool(dev_model and sw.model != dev_model)

                if name_changed or model_changed:
                    old_name = sw.name
                    existing_named = await repo.get_switch_by_name(dev_name)
                    if existing_named is not None and existing_named.id != sw.id:
                        continue

                    if name_changed:
                        sw.name = dev_name
                    if model_changed:
                        sw.model = dev_model
                    sw.updated_at = utc_now()
                    updated_switches.append({
                        "id": str(sw.id),
                        "old_name": old_name,
                        "new_name": sw.name,
                        "ip": sw.ip,
                        "model": sw.model or "",
                    })

    if updated_switches:
        await session.commit()

    await runtime.audit_writer.record(
        user_id=audit_user_id,
        action="switch.synced_from_dataguard",
        target_type="switch",
        ip=request.client.host if request and request.client else None,
        detail={
            "matched_count": matched_count,
            "updated_count": len(updated_switches),
            "devices_total": len(dg_devices),
            **audit_extra,
        },
    )

    msg = f"Sinkronisasi selesai: {len(updated_switches)} switch diperbarui dari {matched_count} switch yang cocok dengan DataGuard."
    return SyncDataGuardResponse(
        success=True,
        updated_count=len(updated_switches),
        matched_count=matched_count,
        devices_total=len(dg_devices),
        updated_switches=updated_switches,
        message=msg,
    )

