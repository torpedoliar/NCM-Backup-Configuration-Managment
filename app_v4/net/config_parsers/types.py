from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VlanDoc:
    id: int
    name: str | None = None


@dataclass
class PortDoc:
    name: str
    description: str | None = None
    enabled: bool = True
    mode: str = "unknown"  # "trunk" | "access" | "unknown"
    native_vlan: int | None = None
    access_vlan: int | None = None
    trunk_allowed_vlans: list[int] = field(default_factory=list)


@dataclass
class ParsedConfig:
    hostname: str | None = None
    vlans: list[VlanDoc] = field(default_factory=list)
    ports: list[PortDoc] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
