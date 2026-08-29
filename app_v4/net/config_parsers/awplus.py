from __future__ import annotations

import re

from app_v4.net.config_parsers._common import expand_id_list, vlan_id_from_token
from app_v4.net.config_parsers.types import ParsedConfig, PortDoc, VlanDoc

_HOSTNAME = re.compile(r"^\s*hostname\s+(\S+)")
_VLAN_NAME = re.compile(r"^\s*vlan\s+(\d+)\s+name\s+(.+?)\s*$")
_PORT_NAME = r"port\d+\.\d+\.\d+"
# 'interface port1.0.1', 'interface port1.0.1-1.0.2', and comma lists of both.
_IFACE_PORT = re.compile(
    rf"^\s*interface\s+({_PORT_NAME}(?:-\d+\.\d+\.\d+)?(?:\s*,\s*{_PORT_NAME}(?:-\d+\.\d+\.\d+)?)*)\s*$"
)


def _unquote(text: str) -> str:
    return text.strip().strip('"')


def _expand_ports(spec: str) -> list[str]:
    """Expand an interface spec like 'port1.0.1-1.0.2,port1.0.5' into names."""
    out: list[str] = []
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        if "-" not in part:
            out.append(part)
            continue
        lo, _, hi = part.partition("-")
        prefix_lo, num_lo = lo.rsplit(".", 1)
        prefix_hi, num_hi = hi.rsplit(".", 1)
        # Range syntax is 'port1.0.1-1.0.2': the 'port' prefix appears only on
        # the lower bound, so compare numeric prefixes.
        if prefix_lo.removeprefix("port") != prefix_hi:
            # Cross-slot range (port1.0.1-port1.1.2) is not modelled; skip.
            continue
        out.extend(f"{prefix_lo}.{n}" for n in range(int(num_lo), int(num_hi) + 1))
    return out


def parse(text: str) -> ParsedConfig:
    cfg = ParsedConfig()
    cur: list[PortDoc] = []
    for raw_line in text.splitlines():
        m = _HOSTNAME.match(raw_line)
        if m and cfg.hostname is None:
            cfg.hostname = m.group(1)
            continue
        m = _VLAN_NAME.match(raw_line)
        if m:
            cfg.vlans.append(VlanDoc(id=int(m.group(1)), name=_unquote(m.group(2))))
            continue
        m = _IFACE_PORT.match(raw_line)
        if m:
            cur = [PortDoc(name=n) for n in _expand_ports(m.group(1))]
            cfg.ports.extend(cur)
            continue
        s = raw_line.strip()
        if s == "!" or s.startswith("interface "):
            cur = []
            continue
        if not cur:
            continue
        if s.startswith("description "):
            d = _unquote(s[len("description "):])
            for p in cur:
                p.description = d
        elif s == "shutdown":
            for p in cur:
                p.enabled = False
        elif s == "switchport mode trunk":
            for p in cur:
                p.mode = "trunk"
        elif s == "switchport mode access":
            for p in cur:
                p.mode = "access"
        elif s.startswith("switchport trunk native vlan "):
            vid = vlan_id_from_token(cfg, s.rsplit(" ", 1)[1], s)
            if vid is not None:
                for p in cur:
                    p.native_vlan = vid
        elif s.startswith("switchport trunk allowed vlan add "):
            vlans = expand_id_list(s.split("add ", 1)[1])
            for p in cur:
                p.trunk_allowed_vlans = list(dict.fromkeys(p.trunk_allowed_vlans + vlans))
        elif s.startswith("switchport access vlan "):
            vid = vlan_id_from_token(cfg, s.rsplit(" ", 1)[1], s)
            if vid is not None:
                for p in cur:
                    p.access_vlan = vid
    return cfg