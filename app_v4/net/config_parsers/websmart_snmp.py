"""Parser for WebSmart-style SNMP MIB dumps.

Unlike the CLI parsers in this package the input here is a saved SNMP walk, not
a running config. The dump is line-oriented:

* ``@ <n> <base-oid>`` sets the base OID that following rows belong to; a bare
  ``@ <n>`` with no OID clears it.
* Data rows are tab-separated: ``<flag>\\t.<col>.<index>\\t<type>\\t[<len>\\t]<value>``.
  ``type == "4"`` is an octet string and carries a declared byte length; every
  other type is a scalar and has no length field.

Octet-string values are binary but the dump was saved as text with a 1:1
byte-to-codepoint mapping, so the original bytes round-trip through
``value.encode("latin-1")``. Because a value may itself contain tab or other
delimiter-looking bytes, the value is taken as the exact declared number of
bytes rather than as "rest of line": extra trailing bytes (a CR from CRLF line
endings, say) are sliced off, while a row carrying fewer bytes than it declares
-- or declaring a negative length -- was truncated or re-encoded, cannot be
trusted, and is skipped with a warning.

A skipped bitmap never costs PVID-derived data. A rejected *untagged* bitmap
additionally suppresses mode derivation for the ports in that VLAN, because
"nobody is untagged here" and "we could not read who is untagged" are not
distinguishable from an absent entry, and guessing would assert a confident
wrong ``trunk``.
"""

from __future__ import annotations

import re

from app_v4.net.config_parsers.types import ParsedConfig, PortDoc, VlanDoc

_VLAN_STATIC_BASE = "1.3.6.1.2.1.17.7.1.4.3.1"
_PORT_VLAN_BASE = "1.3.6.1.2.1.17.7.1.4.5.1"
_INTERESTING_BASES = (_VLAN_STATIC_BASE, _PORT_VLAN_BASE)

# dot1qVlanStaticTable columns.
_COL_VLAN_NAME = "1"
_COL_EGRESS_PORTS = "2"
_COL_UNTAGGED_PORTS = "4"
# dot1qPortVlanTable columns.
_COL_PVID = "1"

_SYSNAME = re.compile(r"1\.3\.6\.1\.2\.1\.1\.5\.0\t[^\t]*\t\s*(\d+)\t(.*)")


def _int_or_warn(cfg: ParsedConfig, token: str, what: str, line: str) -> int | None:
    """Convert a token to int, or record a warning and return None.

    Keeps ``parse`` total: a malformed number is reported as a warning rather
    than raised, so one bad row never costs the caller the whole dump.
    """
    try:
        return int(token)
    except ValueError:
        cfg.warnings.append(f"unparsable {what} {token!r} in row: {line!r}")
        return None


def _bitmap_ports(octets: bytes) -> set[int]:
    """Decode a PortList bitmap: 1 bit per port, MSB of byte 0 is port 1."""
    ports: set[int] = set()
    for i, byte in enumerate(octets):
        for bit in range(8):
            if byte & (0x80 >> bit):
                ports.add(i * 8 + bit + 1)
    return ports


def _octets(cfg: ParsedConfig, value: str, declared: int, line: str) -> bytes | None:
    """Recover the declared number of raw bytes from an octet-string value.

    Returns None (with a warning) when the declared length is negative, or when
    fewer bytes are present than declared, which means the row was truncated or
    re-encoded and its content cannot be trusted.
    """
    raw = value.encode("latin-1", errors="replace")
    if declared < 0:
        # ``raw[:-3]`` would silently drop trailing bytes and look successful.
        cfg.warnings.append(
            f"negative declared length {declared} in row: {line!r}"
        )
        return None
    if len(raw) < declared:
        cfg.warnings.append(
            f"octet string shorter than declared length {declared} "
            f"(got {len(raw)}) in row: {line!r}"
        )
        return None
    return raw[:declared]


def _hostname(text: str) -> str | None:
    m = _SYSNAME.search(text)
    if not m:
        return None
    try:
        declared = int(m.group(1))
    except ValueError:
        return None
    name = m.group(2).encode("latin-1", errors="replace")[:declared]
    return name.decode("latin-1").strip("\x00").strip() or None


def parse(text: str) -> ParsedConfig:
    """Parse a WebSmart SNMP dump into a ``ParsedConfig``.

    Never raises: malformed rows are skipped and reported via ``cfg.warnings``.
    """
    cfg = ParsedConfig()
    cfg.hostname = _hostname(text)

    vlan_names: dict[int, str] = {}
    egress: dict[int, set[int]] = {}
    untagged: dict[int, set[int]] = {}
    # VLANs whose untagged bitmap was rejected. Their egress members cannot be
    # classified tagged-vs-untagged, so no mode may be asserted for them.
    unreadable: set[int] = set()
    pvid: dict[int, int] = {}

    base: str | None = None
    # Lines keep any trailing CR: an octet string may legally end in 0x0d, so
    # trailing bytes are dropped by slicing to the declared length rather than
    # by stripping the line. Scalar fields are stripped individually instead.
    for line in text.split("\n"):
        if line.startswith("@"):
            parts = line.split("\t")
            base = parts[-1].strip() if len(parts) > 1 else None
            continue
        if base not in _INTERESTING_BASES or not line:
            continue

        fields = line.split("\t")
        if len(fields) < 4 or not fields[1].startswith("."):
            continue
        arcs = fields[1].lstrip(".").split(".")
        if len(arcs) < 2:
            continue
        col = arcs[0]
        index = _int_or_warn(cfg, arcs[-1], "OID index", line)
        if index is None:
            continue
        type_code = fields[2].strip()

        if type_code != "4":  # scalar
            if base == _PORT_VLAN_BASE and col == _COL_PVID:
                value = _int_or_warn(cfg, fields[3].strip(), "PVID", line)
                if value is not None:
                    pvid[index] = value
            continue

        # Octet string: fields[3] is the declared length, the value follows.
        declared = _int_or_warn(cfg, fields[3].strip(), "octet string length", line)
        if declared is None:
            continue
        value = "\t".join(fields[4:])
        if base != _VLAN_STATIC_BASE:
            continue
        if col == _COL_VLAN_NAME:
            name = _octets(cfg, value, declared, line)
            if name is not None:
                vlan_names[index] = name.decode("latin-1").strip("\x00").strip()
            continue
        if col not in (_COL_EGRESS_PORTS, _COL_UNTAGGED_PORTS):
            continue
        bitmap = _octets(cfg, value, declared, line)
        if bitmap is None:
            # Membership for this VLAN is unknown, but PVID-derived data for the
            # affected ports is independent and stays intact. A rejected
            # *untagged* bitmap is worse than a missing one: an absent entry is
            # indistinguishable from "no port is untagged here", which would
            # make every egress member look tagged. Record the VLAN so ports
            # touching it decline to assert a mode.
            if col == _COL_UNTAGGED_PORTS:
                unreadable.add(index)
            continue
        target = egress if col == _COL_EGRESS_PORTS else untagged
        target[index] = _bitmap_ports(bitmap)

    cfg.vlans = [VlanDoc(id=v, name=vlan_names[v] or None) for v in sorted(vlan_names)]

    all_ports = sorted(set(pvid) | {p for members in egress.values() for p in members})
    for port in all_ports:
        pd = PortDoc(name=str(port))
        pv = pvid.get(port)
        member = sorted(v for v, ports in egress.items() if port in ports)
        tagged = [v for v in member if port not in untagged.get(v, set())]
        if any(v in unreadable for v in member):
            # At least one VLAN this port belongs to has no trustworthy untagged
            # bitmap, so tagged-vs-untagged cannot be told apart. Assert nothing;
            # the PVID is independent and survives. The rejection was already
            # warned about at the row.
            pd.access_vlan = pv
        elif tagged:
            # Carrying at least one tagged VLAN makes this a trunk; the PVID is
            # then the native (untagged) VLAN.
            pd.mode = "trunk"
            pd.native_vlan = pv
            pd.trunk_allowed_vlans = member
        elif member:
            pd.mode = "access"
            if pv is not None and pv not in member:
                # The switch reports a PVID this port is not a member of. Guess
                # the lowest untagged VLAN, but never discard the PVID silently.
                cfg.warnings.append(
                    f"port {port} PVID {pv} is not in its untagged membership "
                    f"{member}; using access vlan {member[0]}"
                )
            pd.access_vlan = pv if pv in member else member[0]
        elif pv is not None:
            # No usable membership data (no egress bitmap, or it was rejected);
            # the PVID alone still tells us the port's untagged VLAN.
            pd.access_vlan = pv
        cfg.ports.append(pd)

    return cfg
