# Network Documentation API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose each switch's latest successful backup as structured JSON (IP, per-port config, trunk/access status, VLANs), read-only, authenticated with named API keys.

**Architecture:** A pure parser layer (`app_v4/net/config_parsers/`) turns raw backup text into a uniform `ParsedConfig` for three device dialects, auto-detected from content. A new `ApiKey` model + `require_api_key` dependency secures a `/api/v1/network-doc` router that reads the latest successful backup per switch (via existing `Repository.get_latest_backup`), parses it on demand (memoized by `content_hash`), and overlays DB-sourced identity fields.

**Tech Stack:** Python 3, FastAPI, async SQLAlchemy (SQLite), pytest + `fastapi.testclient.TestClient`. Stdlib only (`re`, `hashlib`, `secrets`, `dataclasses`) — no new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-17-network-doc-api-design.md`

## Global Constraints

- No new third-party dependencies — stdlib only.
- Parser functions **never raise** on malformed input; they return a partial `ParsedConfig` and append human-readable strings to `.warnings`.
- Switch `ip`, `name`, `protocol` come from the DB `Switch` row, never from parsed config. The parser fills only config-derived fields (`hostname`, `vlans`, `ports`).
- New `ApiKey` table is created by `Base.metadata.create_all` (already called in `init_db`). No Alembic, no manual migration.
- API errors use `app_v4.service.problem.problem(status, title, detail)` (problem+json), consistent with existing routers.
- Auth/audit follow `app_v4/service/api/switches.py` conventions: `require_role`, `get_db`, `get_runtime`, `runtime.audit_writer.record(...)`.
- Tests extend the existing `app_v4/tests` pytest suite (fixtures `test_settings`, `session_factory` from `conftest.py`; `ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s"*32)`; access token via `runtime.auth_service.issue_access_token(id, username, role)`).
- Port bit numbering for SNMP bitmaps: MSB of byte 0 = port 1.

## File Structure

New:
- `app_v4/net/config_parsers/__init__.py` — `parse_config(text) -> ParsedConfig` + dialect detection.
- `app_v4/net/config_parsers/types.py` — `VlanDoc`, `PortDoc`, `ParsedConfig` dataclasses.
- `app_v4/net/config_parsers/_common.py` — `expand_id_list`, `expand_ports_gN`.
- `app_v4/net/config_parsers/awplus.py` — AlliedWare Plus CLI parser.
- `app_v4/net/config_parsers/dell.py` — Dell-style CLI parser (range replay).
- `app_v4/net/config_parsers/websmart_snmp.py` — WebSmart / V2 SNMP-dump parser.
- `app_v4/service/api/api_keys.py` — API-key management router (admin-only).
- `app_v4/service/api/network_doc.py` — documentation router (`require_api_key`).
- `app_v4/tests/fixtures/network_doc/{awplus,dell,websmart,websmart_v2}.txt` — copied sample backups.
- `app_v4/tests/test_parse_awplus.py`, `test_parse_dell.py`, `test_parse_websmart.py`, `test_parse_dispatch.py`, `test_api_keys.py`, `test_network_doc_api.py`.

Modified:
- `app_v4/data/models.py` — add `ApiKey`.
- `app_v4/data/repository.py` — api-key methods.
- `app_v4/service/deps.py` — `require_api_key`.
- `app_v4/service/app.py` — register the two new routers.

---

### Task 1: Parser types + range helpers

**Files:**
- Create: `app_v4/net/config_parsers/__init__.py` (empty for now — just makes the package importable)
- Create: `app_v4/net/config_parsers/types.py`
- Create: `app_v4/net/config_parsers/_common.py`
- Test: `app_v4/tests/test_parse_common.py`

**Interfaces:**
- Produces:
  - `VlanDoc(id: int, name: str | None = None)`
  - `PortDoc(name: str, description: str | None = None, enabled: bool = True, mode: str = "unknown", native_vlan: int | None = None, access_vlan: int | None = None, trunk_allowed_vlans: list[int] = [])`
  - `ParsedConfig(hostname: str | None = None, vlans: list[VlanDoc] = [], ports: list[PortDoc] = [], warnings: list[str] = [])`
  - `expand_id_list(spec: str) -> list[int]`
  - `expand_ports_gN(spec: str) -> list[str]`

- [ ] **Step 1: Write the failing test**

Create `app_v4/tests/test_parse_common.py`:
```python
from app_v4.net.config_parsers._common import expand_id_list, expand_ports_gN


def test_expand_id_list_mixed_ranges_and_singles():
    assert expand_id_list("4-6,8-12,88") == [4, 5, 6, 8, 9, 10, 11, 12, 88]


def test_expand_id_list_ignores_spaces_and_empty():
    assert expand_id_list(" 1 , 3-4 ,") == [1, 3, 4]


def test_expand_ports_gN():
    assert expand_ports_gN("1-3,6") == ["g1", "g2", "g3", "g6"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest app_v4/tests/test_parse_common.py -v`
Expected: FAIL — `ModuleNotFoundError: app_v4.net.config_parsers._common`

- [ ] **Step 3: Write minimal implementation**

Create `app_v4/net/config_parsers/__init__.py` as an empty file.

Create `app_v4/net/config_parsers/types.py`:
```python
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
```

Create `app_v4/net/config_parsers/_common.py`:
```python
from __future__ import annotations


def expand_id_list(spec: str) -> list[int]:
    """Expand a VLAN/port id spec like '4-6,8-12,88' into a flat int list."""
    out: list[int] = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def expand_ports_gN(spec: str) -> list[str]:
    """Expand a Dell range spec '1-3,6' into ['g1','g2','g3','g6']."""
    return [f"g{n}" for n in expand_id_list(spec)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest app_v4/tests/test_parse_common.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app_v4/net/config_parsers/__init__.py app_v4/net/config_parsers/types.py app_v4/net/config_parsers/_common.py app_v4/tests/test_parse_common.py
git commit -m "feat(net): config-parser types and range helpers"
```

---

### Task 2: AlliedWare Plus parser + fixtures

**Files:**
- Create: `app_v4/net/config_parsers/awplus.py`
- Create: `app_v4/tests/fixtures/network_doc/{awplus,dell,websmart,websmart_v2}.txt` (copied)
- Test: `app_v4/tests/test_parse_awplus.py`

**Interfaces:**
- Consumes: `ParsedConfig`, `PortDoc`, `VlanDoc` (Task 1); `expand_id_list` (Task 1)
- Produces: `parse(text: str) -> ParsedConfig`

- [ ] **Step 1: Copy the sample backups into a test fixtures dir**

Run from the repo root:
```bash
mkdir -p app_v4/tests/fixtures/network_doc
cp "Sample Backup/SSH - Telnet New Switch/013933_running-config.txt" app_v4/tests/fixtures/network_doc/awplus.txt
cp "Sample Backup/SSH - Telnet Old Switch/023913_running-config.txt" app_v4/tests/fixtures/network_doc/dell.txt
cp "Sample Backup/Websmart/002009_running-config.txt" app_v4/tests/fixtures/network_doc/websmart.txt
cp "Sample Backup/Websmart V2/002503_running-config.txt" app_v4/tests/fixtures/network_doc/websmart_v2.txt
```

- [ ] **Step 2: Write the failing test**

Create `app_v4/tests/test_parse_awplus.py`:
```python
from pathlib import Path

from app_v4.net.config_parsers import awplus

FIXTURE = Path(__file__).parent / "fixtures" / "network_doc" / "awplus.txt"


def _port(cfg, name):
    return next(p for p in cfg.ports if p.name == name)


def test_awplus_hostname_and_vlan_names():
    cfg = awplus.parse(FIXTURE.read_text(encoding="utf-8"))
    assert cfg.hostname == "Office2"
    names = {v.id: v.name for v in cfg.vlans}
    assert names[4] == "BOD"
    assert names[88] == "IPH-DEVICE"


def test_awplus_trunk_port_native_and_allowed():
    cfg = awplus.parse(FIXTURE.read_text(encoding="utf-8"))
    p = _port(cfg, "port1.0.1")
    assert p.mode == "trunk"
    assert p.native_vlan == 11
    assert p.trunk_allowed_vlans == [88]
    assert p.enabled is False  # has 'shutdown'


def test_awplus_access_port_and_range_expansion():
    cfg = awplus.parse(FIXTURE.read_text(encoding="utf-8"))
    p6 = _port(cfg, "port1.0.6")
    assert p6.mode == "access"
    assert p6.access_vlan == 11
    p8 = _port(cfg, "port1.0.8")
    assert p8.trunk_allowed_vlans == [4, 5, 9, 14, 15, 18, 20, 24, 25, 27]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest app_v4/tests/test_parse_awplus.py -v`
Expected: FAIL — `ModuleNotFoundError` / `AttributeError: module ... has no attribute 'parse'`

- [ ] **Step 4: Write minimal implementation**

Create `app_v4/net/config_parsers/awplus.py`:
```python
from __future__ import annotations

import re

from app_v4.net.config_parsers._common import expand_id_list
from app_v4.net.config_parsers.types import ParsedConfig, PortDoc, VlanDoc

_HOSTNAME = re.compile(r"^\s*hostname\s+(\S+)")
_VLAN_NAME = re.compile(r"^\s*vlan\s+(\d+)\s+name\s+(.+?)\s*$")
_IFACE_PORT = re.compile(r"^\s*interface\s+(port\d+\.\d+\.\d+)\s*$")


def _unquote(text: str) -> str:
    return text.strip().strip('"')


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
            cur.native_vlan = int(s.rsplit(" ", 1)[1])
        elif s.startswith("switchport trunk allowed vlan add "):
            cur.trunk_allowed_vlans = expand_id_list(s.split("add ", 1)[1])
        elif s.startswith("switchport access vlan "):
            cur.access_vlan = int(s.rsplit(" ", 1)[1])
    return cfg
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest app_v4/tests/test_parse_awplus.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add app_v4/net/config_parsers/awplus.py app_v4/tests/test_parse_awplus.py app_v4/tests/fixtures/network_doc
git commit -m "feat(net): AlliedWare Plus config parser"
```

---

### Task 3: Dell-style parser (range replay)

**Files:**
- Create: `app_v4/net/config_parsers/dell.py`
- Test: `app_v4/tests/test_parse_dell.py`

**Interfaces:**
- Consumes: `ParsedConfig`, `PortDoc`, `VlanDoc` (Task 1); `expand_ports_gN` (Task 1)
- Produces: `parse(text: str) -> ParsedConfig`

- [ ] **Step 1: Write the failing test**

Create `app_v4/tests/test_parse_dell.py`:
```python
from pathlib import Path

from app_v4.net.config_parsers import dell

FIXTURE = Path(__file__).parent / "fixtures" / "network_doc" / "dell.txt"


def _port(cfg, name):
    return next(p for p in cfg.ports if p.name == name)


def test_dell_hostname_and_vlan_names():
    cfg = dell.parse(FIXTURE.read_text(encoding="utf-8"))
    assert cfg.hostname == "Office-1"
    names = {v.id: v.name for v in cfg.vlans}
    assert names[4] == "BOD"
    assert names[88] == "IPH-DEVICE"


def test_dell_access_port_from_range():
    # g7 -> 'switchport access vlan 4'
    cfg = dell.parse(FIXTURE.read_text(encoding="utf-8"))
    p = _port(cfg, "g7")
    assert p.mode == "access"
    assert p.access_vlan == 4


def test_dell_trunk_uplink_allowed_accumulates():
    # g24 is in many 'interface range ethernet g(22-24)' allowed-add blocks
    cfg = dell.parse(FIXTURE.read_text(encoding="utf-8"))
    p = _port(cfg, "g24")
    assert p.mode == "trunk"
    for vlan in (4, 6, 8, 9, 10, 11, 12):
        assert vlan in p.trunk_allowed_vlans
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest app_v4/tests/test_parse_dell.py -v`
Expected: FAIL — module/attribute missing.

- [ ] **Step 3: Write minimal implementation**

Create `app_v4/net/config_parsers/dell.py`:
```python
from __future__ import annotations

import re

from app_v4.net.config_parsers._common import expand_ports_gN
from app_v4.net.config_parsers.types import ParsedConfig, PortDoc, VlanDoc

_HOSTNAME = re.compile(r"^hostname\s+(\S+)")
_IF_RANGE = re.compile(r"^interface range ethernet g\(([^)]*)\)")
_IF_ONE = re.compile(r"^interface ethernet (g\d+)")
_IF_VLAN = re.compile(r"^interface vlan (\d+)")
_VLAN_NAME = re.compile(r"^name\s+(.+)")


def _unquote(text: str) -> str:
    return text.strip().strip('"')


def parse(text: str) -> ParsedConfig:
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
            targets, ctx = [], ("vlan", int(m.group(1)))
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
                v = int(s.rsplit(" ", 1)[1])
                for t in targets:
                    p = get(t)
                    p.mode, p.access_vlan = "access", v
            elif s.startswith("switchport trunk native vlan "):
                v = int(s.rsplit(" ", 1)[1])
                for t in targets:
                    p = get(t)
                    p.native_vlan = v
                    if p.mode == "unknown":
                        p.mode = "trunk"
            elif s.startswith("switchport trunk allowed vlan add "):
                v = int(s.rsplit(" ", 1)[1])
                for t in targets:
                    p = get(t)
                    if v not in p.trunk_allowed_vlans:
                        p.trunk_allowed_vlans.append(v)
                    if p.mode == "unknown":
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest app_v4/tests/test_parse_dell.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app_v4/net/config_parsers/dell.py app_v4/tests/test_parse_dell.py
git commit -m "feat(net): Dell-style config parser with range replay"
```

---

### Task 4: WebSmart SNMP-dump parser

**Files:**
- Create: `app_v4/net/config_parsers/websmart_snmp.py`
- Test: `app_v4/tests/test_parse_websmart.py`

**Interfaces:**
- Consumes: `ParsedConfig`, `PortDoc`, `VlanDoc` (Task 1)
- Produces: `parse(text: str) -> ParsedConfig`

Notes on the dump format (verified against the sample):
- `@ <n> <base-oid>` lines set the current base OID; a bare `@ <n>` clears it (base becomes `None`).
- Data rows: `<flag>\t.<col>.<index>\t<type>\t[<len>\t]<value>`. `type == "4"` is an octet string (has a length field); other types are scalars.
- VLAN static table base `1.3.6.1.2.1.17.7.1.4.3.1`: col `1`=name, col `2`=egress bitmap, col `4`=untagged bitmap.
- Port-VLAN table base `1.3.6.1.2.1.17.7.1.4.5.1`: col `1`=PVID (scalar int).
- Octet-string bytes are recovered by `value.encode("latin-1", errors="replace")`. Validate decoded length == declared length; on mismatch, skip that bitmap and warn (PVID-derived native/access vlan is unaffected).

- [ ] **Step 1: Write the failing test**

Create `app_v4/tests/test_parse_websmart.py`:
```python
from pathlib import Path

from app_v4.net.config_parsers import websmart_snmp

FIXTURE = Path(__file__).parent / "fixtures" / "network_doc" / "websmart.txt"
FIXTURE_V2 = Path(__file__).parent / "fixtures" / "network_doc" / "websmart_v2.txt"


def _port(cfg, name):
    return next(p for p in cfg.ports if p.name == name)


def test_websmart_vlan_names():
    cfg = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    names = {v.id: v.name for v in cfg.vlans}
    assert names[1] == "DefaultVLAN"
    assert names[88] == "IPH-DEVICE"
    assert names[23] == "VIDCON-DEVICE"


def test_websmart_egress_bitmap_decode():
    cfg = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    # vlan 88 egress ffffffffffff0000 -> ports 1..48 all members (trunk allowed)
    trunk_ports_on_88 = [p.name for p in cfg.ports if 88 in p.trunk_allowed_vlans]
    assert len(trunk_ports_on_88) >= 40
    # vlan 23 egress 0000000040010000 -> ports 34, 48
    members_23 = {int(p.name) for p in cfg.ports if 23 in p.trunk_allowed_vlans}
    assert {34, 48}.issubset(members_23) or {34, 48} == members_23


def test_websmart_pvid_gives_native_or_access():
    cfg = websmart_snmp.parse(FIXTURE.read_text(encoding="utf-8"))
    # port 1 PVID=6, port 8 PVID=205 (from dot1qPvid table)
    p1 = _port(cfg, "1")
    assert (p1.native_vlan == 6) or (p1.access_vlan == 6)


def test_websmart_v2_parses_without_error():
    cfg = websmart_snmp.parse(FIXTURE_V2.read_text(encoding="utf-8"))
    assert cfg.ports  # some ports discovered
    assert isinstance(cfg.warnings, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest app_v4/tests/test_parse_websmart.py -v`
Expected: FAIL — module/attribute missing.

- [ ] **Step 3: Write minimal implementation**

Create `app_v4/net/config_parsers/websmart_snmp.py`:
```python
from __future__ import annotations

import re

from app_v4.net.config_parsers.types import ParsedConfig, PortDoc, VlanDoc

_VLAN_STATIC_BASE = "1.3.6.1.2.1.17.7.1.4.3.1"
_PORT_VLAN_BASE = "1.3.6.1.2.1.17.7.1.4.5.1"
_SYSNAME = re.compile(r"1\.3\.6\.1\.2\.1\.1\.5\.0\t[^\t]*\t\s*\d+\t(.+)")


def _bitmap_ports(octets: bytes) -> set[int]:
    ports: set[int] = set()
    for i, byte in enumerate(octets):
        for bit in range(8):
            if byte & (0x80 >> bit):
                ports.add(i * 8 + bit + 1)
    return ports


def parse(text: str) -> ParsedConfig:
    cfg = ParsedConfig()

    m = _SYSNAME.search(text)
    if m:
        cfg.hostname = m.group(1).strip()

    vlan_names: dict[int, str] = {}
    egress: dict[int, set[int]] = {}
    untagged: dict[int, set[int]] = {}
    pvid: dict[int, int] = {}
    bad_bitmaps = 0

    base: str | None = None
    for line in text.split("\n"):
        if line.startswith("@"):
            parts = line.split("\t")
            base = parts[-1].strip() if len(parts) > 1 else None
            continue
        if base not in (_VLAN_STATIC_BASE, _PORT_VLAN_BASE) or not line:
            continue
        f = line.split("\t")
        if len(f) < 4 or not f[1].startswith("."):
            continue
        arcs = f[1].lstrip(".").split(".")
        if len(arcs) < 2:
            continue
        col, index = arcs[0], int(arcs[-1])
        type_code = f[2].strip()

        if type_code == "4":  # octet string: f[3]=len, rest=value
            if len(f) < 5:
                continue
            declared = int(f[3].strip())
            value = "\t".join(f[4:])
            octets = value.encode("latin-1", errors="replace")
            if base == _VLAN_STATIC_BASE and col == "1":
                vlan_names[index] = value
                continue
            if len(octets) != declared:
                bad_bitmaps += 1
                continue
            if base == _VLAN_STATIC_BASE and col == "2":
                egress[index] = _bitmap_ports(octets)
            elif base == _VLAN_STATIC_BASE and col == "4":
                untagged[index] = _bitmap_ports(octets)
        else:  # scalar
            value = f[3].strip()
            if base == _PORT_VLAN_BASE and col == "1":
                pvid[index] = int(value)

    cfg.vlans = [VlanDoc(id=v, name=vlan_names[v]) for v in sorted(vlan_names)]

    all_ports = sorted(set(pvid) | {p for members in egress.values() for p in members})
    for port in all_ports:
        pd = PortDoc(name=str(port))
        pv = pvid.get(port)
        member = [v for v, ps in egress.items() if port in ps]
        tagged = [v for v in member if port not in untagged.get(v, set())]
        if tagged:
            pd.mode = "trunk"
            pd.native_vlan = pv
            pd.trunk_allowed_vlans = sorted(member)
        elif member:
            pd.mode = "access"
            pd.access_vlan = pv if pv in member else member[0]
        else:
            # No egress membership seen for this port; fall back to PVID.
            pd.mode = "access" if pv is not None else "unknown"
            pd.access_vlan = pv
        cfg.ports.append(pd)

    if bad_bitmaps:
        cfg.warnings.append(
            f"{bad_bitmaps} VLAN port bitmap(s) unreadable; affected port modes "
            "derive from PVID only"
        )
    return cfg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest app_v4/tests/test_parse_websmart.py -v`
Expected: PASS (4 tests). If `test_websmart_egress_bitmap_decode` fails, print `sorted(members_23)` and confirm the fixture's `.2.23` row — decoded ports must be `{34, 48}`.

- [ ] **Step 5: Commit**

```bash
git add app_v4/net/config_parsers/websmart_snmp.py app_v4/tests/test_parse_websmart.py
git commit -m "feat(net): WebSmart SNMP-dump parser"
```

---

### Task 5: Dialect dispatcher

**Files:**
- Modify: `app_v4/net/config_parsers/__init__.py`
- Test: `app_v4/tests/test_parse_dispatch.py`

**Interfaces:**
- Consumes: `awplus.parse`, `dell.parse`, `websmart_snmp.parse` (Tasks 2–4); `ParsedConfig` (Task 1)
- Produces: `parse_config(text: str) -> ParsedConfig`, `detect_dialect(text: str) -> str`

- [ ] **Step 1: Write the failing test**

Create `app_v4/tests/test_parse_dispatch.py`:
```python
from pathlib import Path

from app_v4.net.config_parsers import detect_dialect, parse_config

FX = Path(__file__).parent / "fixtures" / "network_doc"


def test_detect_dialect():
    assert detect_dialect((FX / "awplus.txt").read_text(encoding="utf-8")) == "awplus"
    assert detect_dialect((FX / "dell.txt").read_text(encoding="utf-8")) == "dell"
    assert detect_dialect((FX / "websmart.txt").read_text(encoding="utf-8")) == "websmart"
    assert detect_dialect((FX / "websmart_v2.txt").read_text(encoding="utf-8")) == "websmart"


def test_parse_config_routes_each_dialect():
    for name in ("awplus", "dell", "websmart", "websmart_v2"):
        cfg = parse_config((FX / f"{name}.txt").read_text(encoding="utf-8"))
        assert cfg.ports, f"{name} produced no ports"


def test_parse_config_unknown_is_warning_not_error():
    cfg = parse_config("this is not a switch config at all\n")
    assert cfg.ports == []
    assert cfg.warnings
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest app_v4/tests/test_parse_dispatch.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_config'`.

- [ ] **Step 3: Write minimal implementation**

Replace `app_v4/net/config_parsers/__init__.py` with:
```python
from __future__ import annotations

from app_v4.net.config_parsers import awplus, dell, websmart_snmp
from app_v4.net.config_parsers.types import ParsedConfig, PortDoc, VlanDoc

__all__ = ["parse_config", "detect_dialect", "ParsedConfig", "PortDoc", "VlanDoc"]


def detect_dialect(text: str) -> str:
    if "interface port1.0." in text:
        return "awplus"
    if "interface range ethernet g(" in text or "interface ethernet g" in text:
        return "dell"
    head = text[:200]
    if "@" in head and "1.3.6.1" in text:
        return "websmart"
    return "unknown"


def parse_config(text: str) -> ParsedConfig:
    dialect = detect_dialect(text)
    if dialect == "awplus":
        return awplus.parse(text)
    if dialect == "dell":
        return dell.parse(text)
    if dialect == "websmart":
        return websmart_snmp.parse(text)
    return ParsedConfig(warnings=["unknown switch config dialect; nothing parsed"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest app_v4/tests/test_parse_dispatch.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the whole parser suite**

Run: `python -m pytest app_v4/tests/test_parse_common.py app_v4/tests/test_parse_awplus.py app_v4/tests/test_parse_dell.py app_v4/tests/test_parse_websmart.py app_v4/tests/test_parse_dispatch.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app_v4/net/config_parsers/__init__.py app_v4/tests/test_parse_dispatch.py
git commit -m "feat(net): dialect detection and parse_config dispatcher"
```

---

### Task 6: ApiKey model + repository methods

**Files:**
- Modify: `app_v4/data/models.py` (add `ApiKey` after `AuditLog`)
- Modify: `app_v4/data/repository.py` (add api-key methods; import `ApiKey`)
- Test: `app_v4/tests/test_repository_api_keys.py`

**Interfaces:**
- Produces:
  - `ApiKey` model: `id, name, key_hash, prefix, created_at, last_used_at, revoked`
  - `Repository.create_api_key(name: str, key_hash: str, prefix: str) -> ApiKey`
  - `Repository.list_api_keys() -> list[ApiKey]`
  - `Repository.get_api_key_by_hash(key_hash: str) -> ApiKey | None`
  - `Repository.revoke_api_key(key_id: int) -> bool`
  - `Repository.touch_api_key_last_used(key_id: int) -> None`

- [ ] **Step 1: Write the failing test**

Create `app_v4/tests/test_repository_api_keys.py`:
```python
import pytest

from app_v4.data.repository import Repository


@pytest.mark.asyncio
async def test_create_and_lookup_api_key(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        created = await repo.create_api_key(name="netdoc", key_hash="abc123", prefix="ncr_1234")
        await session.commit()
        assert created.id is not None

    async with session_factory() as session:
        repo = Repository(session)
        found = await repo.get_api_key_by_hash("abc123")
        assert found is not None and found.name == "netdoc"
        assert await repo.get_api_key_by_hash("nope") is None


@pytest.mark.asyncio
async def test_revoke_hides_from_lookup(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        key = await repo.create_api_key(name="x", key_hash="h", prefix="p")
        await session.commit()
        key_id = key.id

    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.revoke_api_key(key_id) is True
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        assert await repo.get_api_key_by_hash("h") is None  # revoked excluded
        assert [k.revoked for k in await repo.list_api_keys()] == [True]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest app_v4/tests/test_repository_api_keys.py -v`
Expected: FAIL — `AttributeError: 'Repository' object has no attribute 'create_api_key'`.

- [ ] **Step 3: Add the model**

In `app_v4/data/models.py`, append after the `AuditLog` class:
```python
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

- [ ] **Step 4: Add repository methods**

In `app_v4/data/repository.py`, add `ApiKey` to the models import line, then add these methods to the `Repository` class (e.g. after the credential methods):
```python
    # ----- api keys -----

    async def create_api_key(self, name: str, key_hash: str, prefix: str) -> ApiKey:
        key = ApiKey(name=name, key_hash=key_hash, prefix=prefix)
        self.session.add(key)
        await self.session.flush()
        return key

    async def list_api_keys(self) -> list[ApiKey]:
        result = await self.session.execute(select(ApiKey).order_by(ApiKey.created_at))
        return list(result.scalars().all())

    async def get_api_key_by_name(self, name: str) -> ApiKey | None:
        result = await self.session.execute(select(ApiKey).where(ApiKey.name == name))
        return result.scalar_one_or_none()

    async def get_api_key_by_hash(self, key_hash: str) -> ApiKey | None:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked.is_(False))
        )
        return result.scalar_one_or_none()

    async def revoke_api_key(self, key_id: int) -> bool:
        key = await self.session.get(ApiKey, key_id)
        if key is None:
            return False
        key.revoked = True
        return True

    async def touch_api_key_last_used(self, key_id: int) -> None:
        key = await self.session.get(ApiKey, key_id)
        if key is not None:
            key.last_used_at = datetime.utcnow()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest app_v4/tests/test_repository_api_keys.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add app_v4/data/models.py app_v4/data/repository.py app_v4/tests/test_repository_api_keys.py
git commit -m "feat(data): ApiKey model and repository methods"
```

---

### Task 7: require_api_key dependency

**Files:**
- Modify: `app_v4/service/deps.py`
- Test: `app_v4/tests/test_require_api_key.py`

**Interfaces:**
- Consumes: `Repository.get_api_key_by_hash`, `Repository.touch_api_key_last_used` (Task 6); `get_db`, `problem`
- Produces: `require_api_key(...) -> str` (returns the authenticated key's `name`). Accepts `Authorization: Bearer <key>` or `X-API-Key: <key>`.

- [ ] **Step 1: Write the failing test**

Create `app_v4/tests/test_require_api_key.py`:
```python
import hashlib

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.deps import get_runtime, require_api_key
from app_v4.service.runtime import ServiceRuntime


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _app(runtime: ServiceRuntime) -> FastAPI:
    app = FastAPI()
    app.state.runtime = runtime

    @app.get("/probe")
    async def probe(name: str = Depends(require_api_key)):
        return {"name": name}

    return app


@pytest.mark.asyncio
async def test_valid_key_passes(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_api_key(name="netdoc", key_hash=_hash("secret-key"), prefix="ncr_secr")
        await session.commit()

    client = TestClient(_app(runtime))
    r1 = client.get("/probe", headers={"Authorization": "Bearer secret-key"})
    r2 = client.get("/probe", headers={"X-API-Key": "secret-key"})
    assert r1.status_code == 200 and r1.json()["name"] == "netdoc"
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_missing_or_bad_key_rejected(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    client = TestClient(_app(runtime))
    assert client.get("/probe").status_code == 401
    assert client.get("/probe", headers={"X-API-Key": "wrong"}).status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest app_v4/tests/test_require_api_key.py -v`
Expected: FAIL — `ImportError: cannot import name 'require_api_key'`.

- [ ] **Step 3: Add the dependency**

In `app_v4/service/deps.py`, add imports and the dependency:
```python
import hashlib

from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.data.repository import Repository


async def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> str:
    presented = x_api_key
    if presented is None and authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    if not presented:
        raise problem(401, "Unauthorized", "Missing API key")
    key_hash = hashlib.sha256(presented.encode("utf-8")).hexdigest()
    repo = Repository(session)
    key = await repo.get_api_key_by_hash(key_hash)
    if key is None:
        raise problem(401, "Unauthorized", "Invalid or revoked API key")
    await repo.touch_api_key_last_used(key.id)
    await session.commit()
    return key.name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest app_v4/tests/test_require_api_key.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/deps.py app_v4/tests/test_require_api_key.py
git commit -m "feat(service): require_api_key dependency (Bearer or X-API-Key)"
```

---

### Task 8: API-key management router

**Files:**
- Create: `app_v4/service/api/api_keys.py`
- Modify: `app_v4/service/app.py` (register router)
- Test: `app_v4/tests/test_api_keys.py`

**Interfaces:**
- Consumes: `Repository` api-key methods (Task 6); `require_role`, `get_db`, `get_runtime`, `problem`
- Produces: router with `POST /api/v1/api-keys`, `GET /api/v1/api-keys`, `DELETE /api/v1/api-keys/{key_id}`. `POST` returns `{id, name, prefix, key}` — the plaintext `key` appears only here.

- [ ] **Step 1: Write the failing test**

Create `app_v4/tests/test_api_keys.py`:
```python
import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime


def _admin_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(1, "admin", "admin")


def _viewer_token(runtime: ServiceRuntime) -> str:
    return runtime.auth_service.issue_access_token(2, "viewer", "viewer")


@pytest.mark.asyncio
async def test_create_lists_and_revoke(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        await Repository(session).create_user("admin", "h", "admin")
        await session.commit()
    client = TestClient(create_app(runtime))
    hdr = {"Authorization": f"Bearer {_admin_token(runtime)}"}

    created = client.post("/api/v1/api-keys", headers=hdr, json={"name": "netdoc"})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "netdoc"
    assert body["key"].startswith("ncr_")  # plaintext shown once

    listed = client.get("/api/v1/api-keys", headers=hdr)
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "netdoc"
    assert "key" not in listed.json()[0]  # never returns plaintext again

    key_id = body["id"]
    assert client.delete(f"/api/v1/api-keys/{key_id}", headers=hdr).status_code == 204


@pytest.mark.asyncio
async def test_viewer_forbidden(test_settings, session_factory):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    async with session_factory() as session:
        await Repository(session).create_user("viewer", "h", "viewer")
        await session.commit()
    client = TestClient(create_app(runtime))
    r = client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {_viewer_token(runtime)}"},
        json={"name": "x"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest app_v4/tests/test_api_keys.py -v`
Expected: FAIL — 404 on the endpoint (router not registered).

- [ ] **Step 3: Write the router**

Create `app_v4/service/api/api_keys.py`:
```python
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app_v4.core.auth_service import AccessClaims
from app_v4.data.repository import Repository
from app_v4.service.deps import get_db, get_runtime, require_role
from app_v4.service.problem import problem
from app_v4.service.runtime import ServiceRuntime

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    prefix: str
    key: str


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked: bool


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> ApiKeyCreated:
    repo = Repository(session)
    if await repo.get_api_key_by_name(payload.name) is not None:
        raise problem(409, "Conflict", "API key name already exists")
    plaintext = "ncr_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    prefix = plaintext[:8]
    key = await repo.create_api_key(name=payload.name, key_hash=key_hash, prefix=prefix)
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="apikey.created",
        target_type="api_key",
        target_id=str(key.id),
        ip=request.client.host if request.client else None,
        detail={"name": key.name},
    )
    return ApiKeyCreated(id=key.id, name=key.name, prefix=prefix, key=plaintext)


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    session: AsyncSession = Depends(get_db),
    _actor: AccessClaims = Depends(require_role("admin")),
) -> list[ApiKeyOut]:
    repo = Repository(session)
    return [
        ApiKeyOut(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            revoked=k.revoked,
        )
        for k in await repo.list_api_keys()
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    actor: AccessClaims = Depends(require_role("admin")),
) -> Response:
    repo = Repository(session)
    if not await repo.revoke_api_key(key_id):
        raise problem(404, "Not Found", "API key not found")
    await session.commit()
    await runtime.audit_writer.record(
        user_id=actor.user_id,
        action="apikey.revoked",
        target_type="api_key",
        target_id=str(key_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Register the router**

In `app_v4/service/app.py`, extend the import line and add the include (keep them grouped with the others):
```python
    from app_v4.service.api import (
        api_keys,
        audit,
        auth,
        autostart,
        backups,
        credentials,
        jobs,
        switches,
        system,
        users,
        ws,
    )

    app.include_router(api_keys.router, prefix="/api/v1")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest app_v4/tests/test_api_keys.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add app_v4/service/api/api_keys.py app_v4/service/app.py app_v4/tests/test_api_keys.py
git commit -m "feat(api): admin-managed named API keys"
```

---

### Task 9: network-doc router

**Files:**
- Create: `app_v4/service/api/network_doc.py`
- Modify: `app_v4/service/app.py` (register router)
- Test: `app_v4/tests/test_network_doc_api.py`

**Interfaces:**
- Consumes: `parse_config` (Task 5); `require_api_key` (Task 7); `Repository.list_switches`, `Repository.get_switch`, `Repository.get_latest_backup`; `get_db`, `problem`
- Produces: `GET /api/v1/network-doc`, `GET /api/v1/network-doc/{switch_id}`.

- [ ] **Step 1: Write the failing test**

Create `app_v4/tests/test_network_doc_api.py`:
```python
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_v4.data.repository import Repository
from app_v4.service.app import create_app
from app_v4.service.runtime import ServiceRuntime

FX = Path(__file__).parent / "fixtures" / "network_doc"


def _key_headers() -> dict:
    return {"X-API-Key": "netdoc-secret"}


async def _seed(session_factory, tmp_path) -> None:
    backup_file = tmp_path / "awplus.txt"
    backup_file.write_text((FX / "awplus.txt").read_text(encoding="utf-8"), encoding="utf-8")
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_api_key(
            name="netdoc",
            key_hash=hashlib.sha256(b"netdoc-secret").hexdigest(),
            prefix="netd",
        )
        cred = await repo.create_credential(name="lab", enc_blob=b"x")
        sw = await repo.create_switch(name="Office2", ip="10.10.0.6", protocol="ssh", port=22, credential_id=cred.id)
        await session.flush()
        await repo.create_backup(
            switch_id=sw.id,
            file_path=str(backup_file),
            content_hash="hash-office2",
            size_bytes=100,
            success=True,
            message="ok",
            backup_type="manual",
        )
        await session.commit()


@pytest.mark.asyncio
async def test_network_doc_requires_api_key(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    await _seed(session_factory, tmp_path)
    client = TestClient(create_app(runtime))
    assert client.get("/api/v1/network-doc").status_code == 401


@pytest.mark.asyncio
async def test_network_doc_returns_parsed_switch(test_settings, session_factory, tmp_path):
    runtime = ServiceRuntime.for_tests(test_settings, session_factory, jwt_secret=b"s" * 32)
    await _seed(session_factory, tmp_path)
    client = TestClient(create_app(runtime))

    r = client.get("/api/v1/network-doc", headers=_key_headers())
    assert r.status_code == 200
    doc = r.json()[0]
    assert doc["ip"] == "10.10.0.6"          # from DB, not parsed
    assert doc["name"] == "Office2"
    assert any(v["id"] == 88 and v["name"] == "IPH-DEVICE" for v in doc["vlans"])
    p1 = next(p for p in doc["ports"] if p["name"] == "port1.0.1")
    assert p1["mode"] == "trunk" and p1["native_vlan"] == 11
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest app_v4/tests/test_network_doc_api.py -v`
Expected: FAIL — 404 (router not registered).

- [ ] **Step 3: Write the router**

Create `app_v4/service/api/network_doc.py`:
```python
from __future__ import annotations

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

# ponytail: unbounded process-lifetime cache keyed by backup content_hash.
# Bounded in practice by the number of distinct config versions. Swap for an
# LRU if a deployment ever accumulates too many entries.
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
        path = Path(backup.file_path) if backup.file_path else None
        if path and path.exists():
            cfg = _parse_cached(backup.content_hash, path.read_text(encoding="utf-8"))
        else:
            cfg = ParsedConfig(warnings=["backup file missing on disk"])
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
    return [await _build_doc(repo, s) for s in switches]


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
```

- [ ] **Step 4: Register the router**

In `app_v4/service/app.py`, add `network_doc` to the `from app_v4.service.api import (...)` group and add:
```python
    app.include_router(network_doc.router, prefix="/api/v1")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest app_v4/tests/test_network_doc_api.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Run the full backend suite for regressions**

Run: `python -m pytest app_v4/tests -q`
Expected: all PASS (no regressions in existing tests; note `test_backend_spec_contract.py` may enumerate routes — if it asserts an exact route set, update it to include the two new routers).

- [ ] **Step 7: Commit**

```bash
git add app_v4/service/api/network_doc.py app_v4/service/app.py app_v4/tests/test_network_doc_api.py
git commit -m "feat(api): network-doc endpoints (structured latest-backup docs)"
```

---

### Task 10 (optional): Settings web UI — API keys section

Backend is fully usable without this (keys can be created via `POST /api/v1/api-keys`). Implement only if a self-service UI is wanted.

**Files:**
- Modify: `app_v4/web/src/api/types.ts` (add `ApiKey`, `ApiKeyCreated` types)
- Modify: `app_v4/web/src/api/hooks.ts` (add `useApiKeys`, `useCreateApiKey`, `useRevokeApiKey`)
- Modify: `app_v4/web/src/pages/SettingsPage.tsx` (add an "API Keys" section)
- Test: extend an existing settings test (follow `app_v4/web/src/pages/settings/SettingsAuthSection.test.tsx` patterns)

**Interfaces:**
- Consumes: `GET/POST/DELETE /api/v1/api-keys` (Task 8)

- [ ] **Step 1:** Read `app_v4/web/src/api/hooks.ts` and `app_v4/web/src/pages/settings/SettingsAuthSection.test.tsx` to match the existing React Query + component + test conventions before writing anything.
- [ ] **Step 2:** Write a failing component test: rendering the section lists keys from a mocked `GET /api/v1/api-keys`, and clicking "Create" shows the one-time plaintext key from the mocked `POST` response.
- [ ] **Step 3:** Add the `ApiKey` / `ApiKeyCreated` types to `types.ts` matching the `ApiKeyOut` / `ApiKeyCreated` shapes from Task 8.
- [ ] **Step 4:** Add `useApiKeys` (query), `useCreateApiKey` (mutation, invalidates the list), `useRevokeApiKey` (mutation, invalidates the list) to `hooks.ts`.
- [ ] **Step 5:** Add the "API Keys" section to `SettingsPage.tsx`: table of `name / prefix / created / last used / revoked` + a create form (name input) that surfaces the returned plaintext key once with a copy button + a revoke action per row.
- [ ] **Step 6:** Run the web test suite: `cd app_v4/web && npm test`. Expected: PASS.
- [ ] **Step 7: Commit**

```bash
git add app_v4/web/src/api/types.ts app_v4/web/src/api/hooks.ts app_v4/web/src/pages/SettingsPage.tsx
git commit -m "feat(web): API keys section in Settings"
```

---

## Self-Review

**Spec coverage:**
- §4.1 parser layer + detection → Tasks 1–5. ✓
- §4.2 output shape → `PortDoc`/`VlanDoc`/`ParsedConfig` (Task 1) + `SwitchDoc` (Task 9). ✓
- §5.1 AWPlus / §5.2 Dell / §5.3 WebSmart → Tasks 2, 3, 4 (incl. latin-1 recovery, length validation, PVID fallback). ✓
- §6 API-key auth (model, dependency, management endpoints) → Tasks 6, 7, 8. ✓
- §6.4 Web UI → Task 10 (optional, as the spec marks it trimmable). ✓
- §7 endpoints + content_hash cache → Task 9. ✓
- §8 wiring/repository → Tasks 6, 8, 9. ✓
- §9 error handling (parsers never raise; missing file → warning + 200; 401 on auth) → Tasks 5, 7, 9. ✓
- §10 testing → one test module per parser + auth + api. ✓

**Placeholder scan:** No TBD/TODO; every code and test step contains full content. ✓

**Type consistency:** `parse(text)` used consistently for per-dialect parsers; `parse_config(text)`/`detect_dialect(text)` in the dispatcher; `ParsedConfig.warnings` → `SwitchDoc.parse_warnings` mapping is explicit in `_build_doc`; repository method names match between Tasks 6, 7, 8, 9. ✓

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-17-network-doc-api.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
