from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.data.repository import Repository
from app_v4.net.config_parsers import ParsedConfig, parse_config
from app_v4.service.deps import get_db, require_api_key
from app_v4.service.problem import problem

router = APIRouter(prefix="/network-doc", tags=["network-doc"])
logger = logging.getLogger(__name__)

# Cache only parsed configuration content. Database identity is overlaid for every
# response so matching backup hashes can never cross-contaminate switch metadata.
_PARSE_CACHE: dict[str, ParsedConfig] = {}


class VlanOut(BaseModel):
    id: int
    name: str | None


class PortOut(BaseModel):
    name: str
    description: str | None
    enabled: bool
    mode: str
    native_vlan: int | None
    access_vlan: int | None
    trunk_allowed_vlans: list[int]


class SwitchDoc(BaseModel):
    switch_id: int
    name: str
    ip: str
    protocol: str
    hostname: str | None
    source_backup_id: int | None
    backup_taken_at: datetime | None
    vlans: list[VlanOut]
    ports: list[PortOut]
    parse_warnings: list[str]


def _parse_cached(content_hash: str, text: str) -> ParsedConfig:
    if content_hash and content_hash in _PARSE_CACHE:
        return _PARSE_CACHE[content_hash]
    cfg = parse_config(text)
    if content_hash:
        _PARSE_CACHE[content_hash] = cfg
    return cfg


async def _build_doc(repo: Repository, switch) -> SwitchDoc:
    backup = await repo.get_latest_backup(switch.id)
    cfg = ParsedConfig(warnings=["no successful backup"])
    backup_id = None
    taken_at = None

    if backup is not None:
        backup_id = backup.id
        taken_at = backup.taken_at
        try:
            path = Path(backup.file_path) if backup.file_path else None
            if path is None or not path.is_file():
                cfg = ParsedConfig(warnings=["backup file missing on disk"])
            else:
                cfg = _parse_cached(backup.content_hash, path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            logger.exception("Unable to parse network documentation backup for switch %s", switch.id)
            cfg = ParsedConfig(warnings=["unable to parse backup"])
        except Exception:
            # Parser failures are isolated per switch so bulk documentation remains available.
            logger.exception("Unable to parse network documentation backup for switch %s", switch.id)
            cfg = ParsedConfig(warnings=["unable to parse backup"])

    return SwitchDoc(
        switch_id=switch.id,
        name=switch.name,
        ip=switch.ip,
        protocol=switch.protocol,
        hostname=cfg.hostname,
        source_backup_id=backup_id,
        backup_taken_at=taken_at,
        vlans=[VlanOut(id=v.id, name=v.name) for v in cfg.vlans],
        ports=[
            PortOut(
                name=p.name,
                description=p.description,
                enabled=p.enabled,
                mode=p.mode,
                native_vlan=p.native_vlan,
                access_vlan=p.access_vlan,
                trunk_allowed_vlans=p.trunk_allowed_vlans,
            )
            for p in cfg.ports
        ],
        parse_warnings=cfg.warnings,
    )


@router.get("", response_model=list[SwitchDoc])
async def list_network_doc(
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> list[SwitchDoc]:
    repo = Repository(session)
    switches = await repo.list_switches(include_inactive=False)
    return [await _build_doc(repo, switch) for switch in switches]


@router.get("/{switch_id}", response_model=SwitchDoc)
async def get_network_doc(
    switch_id: int,
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> SwitchDoc:
    repo = Repository(session)
    switch = await repo.get_switch(switch_id)
    if switch is None:
        raise problem(404, "Not Found", "Switch not found")
    return await _build_doc(repo, switch)
