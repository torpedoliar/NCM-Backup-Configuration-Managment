from __future__ import annotations

import re

from app_v4.net.config_parsers._common import expand_id_list
from app_v4.net.config_parsers.types import ParsedConfig, PortDoc, VlanDoc

_HOSTNAME = re.compile(r"^\s*hostname\s+(\S+)")
_VLAN_NAME = re.compile(r"^\s*vlan\s+(\d+)\s+name\s+(.+?)\s*$")
_IFACE_PORT = re.compile(r"^\s*interface\s+(port\d+\.\d+\.\d+)\s*$")


def _unquote(text: str) -> str:
    return text.strip().strip('"')


def _vlan_id(cfg: ParsedConfig, line: str) -> int | None:
    """Parse the trailing vlan id of a switchport line, or warn and return None.

    Keeps ``parse`` total: a malformed id is recorded as a warning rather than
    raised, so a single bad line never costs the caller the whole config.
    """
    token = line.rsplit(" ", 1)[1]
    try:
        return int(token)
    except ValueError:
        cfg.warnings.append(f"unparsable vlan id {token!r} in line: {line}")
        return None


def parse(text: str) -> ParsedConfig:
    cfg = ParsedConfig()
    cur: PortDoc | None = None
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
            cur = PortDoc(name=m.group(1))
            cfg.ports.append(cur)
            continue
        s = raw_line.strip()
        if s == "!" or s.startswith("interface "):
            cur = None
            continue
        if cur is None:
            continue
        if s.startswith("description "):
            cur.description = _unquote(s[len("description "):])
        elif s == "shutdown":
            cur.enabled = False
        elif s == "switchport mode trunk":
            cur.mode = "trunk"
        elif s == "switchport mode access":
            cur.mode = "access"
        elif s.startswith("switchport trunk native vlan "):
            vid = _vlan_id(cfg, s)
            if vid is not None:
                cur.native_vlan = vid
        elif s.startswith("switchport trunk allowed vlan add "):
            cur.trunk_allowed_vlans = expand_id_list(s.split("add ", 1)[1])
        elif s.startswith("switchport access vlan "):
            vid = _vlan_id(cfg, s)
            if vid is not None:
                cur.access_vlan = vid
    return cfg
