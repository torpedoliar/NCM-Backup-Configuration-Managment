from __future__ import annotations

import re

from app_v4.net.config_parsers._common import expand_id_list, expand_ports_gN, vlan_id_from_token
from app_v4.net.config_parsers.types import ParsedConfig, PortDoc, VlanDoc

_HOSTNAME = re.compile(r"^hostname\s+(\S+)")
_IF_RANGE = re.compile(r"^interface range ethernet g\(([^)]*)\)")
_IF_ONE = re.compile(r"^interface ethernet (g\d+)")
_IF_VLAN = re.compile(r"^interface vlan (\S+)")
_VLAN_NAME = re.compile(r"^name\s+(.+)")


def _unquote(text: str) -> str:
    return text.strip().strip('"')


def parse(text: str) -> ParsedConfig:
    """Parse a Dell-style running config by replaying commands onto port state.

    Dell configs configure ports cumulatively: ``interface range ethernet
    g(...)`` blocks scattered across the file each apply settings to every port
    in the range, in file order. Ports are therefore accumulated in a dict and
    mutated as the replay proceeds, rather than built once per block.
    """
    cfg = ParsedConfig()
    ports: dict[str, PortDoc] = {}

    def get(name: str) -> PortDoc:
        if name not in ports:
            ports[name] = PortDoc(name=name)
        return ports[name]

    targets: list[str] = []
    ctx: str | tuple[str, int] | None = None

    for raw_line in text.splitlines():
        s = raw_line.strip()
        m = _HOSTNAME.match(s)
        if m:
            cfg.hostname = m.group(1)
            continue
        m = _IF_RANGE.match(s)
        if m:
            targets, ctx = expand_ports_gN(m.group(1)), "port"
            continue
        m = _IF_ONE.match(s)
        if m:
            targets, ctx = [m.group(1)], "port"
            continue
        m = _IF_VLAN.match(s)
        if m:
            vid = vlan_id_from_token(cfg, m.group(1), s)
            targets, ctx = [], None if vid is None else ("vlan", vid)
            continue
        if s.startswith("interface "):
            # An interface form we do not model (port-channel, slot syntax like
            # 'ethernet 1/g5', ...) still opens a block. Reset context so its
            # body is dropped rather than misattributed to the previous block.
            targets, ctx = [], None
            continue
        if s == "exit":
            targets, ctx = [], None
            continue

        if ctx == "port":
            if s == "switchport mode trunk":
                for t in targets:
                    if get(t).mode == "unknown":
                        get(t).mode = "trunk"
            elif s.startswith("switchport access vlan "):
                v = vlan_id_from_token(cfg, s.rsplit(" ", 1)[1], s)
                if v is not None:
                    for t in targets:
                        p = get(t)
                        p.mode, p.access_vlan = "access", v
            elif s.startswith("switchport trunk native vlan "):
                v = vlan_id_from_token(cfg, s.rsplit(" ", 1)[1], s)
                if v is not None:
                    for t in targets:
                        p = get(t)
                        p.native_vlan = v
                        if p.mode == "unknown":
                            p.mode = "trunk"
            elif s.startswith("switchport trunk allowed vlan add "):
                spec = s.split("add ", 1)[1]
                vlans = expand_id_list(spec)
                if not vlans:
                    cfg.warnings.append(
                        f"unparsable vlan id {spec!r} in line: {s}"
                    )
                for t in targets:
                    p = get(t)
                    # 'add' accumulates: a port may be named by several
                    # add lines and each one extends the allowed set.
                    for v in vlans:
                        if v not in p.trunk_allowed_vlans:
                            p.trunk_allowed_vlans.append(v)
                    if vlans and p.mode == "unknown":
                        p.mode = "trunk"
            elif s.startswith("description "):
                d = _unquote(s[len("description "):])
                for t in targets:
                    get(t).description = d
        elif isinstance(ctx, tuple) and ctx[0] == "vlan":
            m = _VLAN_NAME.match(s)
            if m:
                cfg.vlans.append(VlanDoc(id=ctx[1], name=_unquote(m.group(1))))

    for p in ports.values():
        p.trunk_allowed_vlans.sort()
    cfg.ports = [ports[k] for k in sorted(ports, key=lambda g: int(g[1:]))]
    return cfg
