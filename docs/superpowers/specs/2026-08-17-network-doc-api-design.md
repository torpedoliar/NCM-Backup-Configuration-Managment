# Network Documentation API — Design Spec

Date: 2026-08-17
Status: Approved for planning

## 1. Purpose

Expose the latest backed-up configuration of every switch as structured
JSON so an external network-documentation application can consume it.
Per switch the API reports: IP, per-port configuration, trunk/access
status, and VLAN assignment (native vlan, trunk-allowed vlans, access
vlan) plus the VLAN name table.

Read-only. Authenticated with named API keys (machine-to-machine).

## 2. Goals / Non-goals

Goals:
- Parse the latest **successful** backup of each active switch into a
  uniform structured shape, regardless of device dialect.
- Cover all four device families present today: AlliedWare Plus CLI,
  Dell-style CLI, WebSmart SNMP dump, WebSmart V2 SNMP dump.
- Named API-key auth, admin-managed, revocable.

Non-goals (YAGNI for v1):
- No write/config-push. No historical/diff endpoints (already exist
  elsewhere). No parse-at-backup-time storage. No per-VLAN topology
  graph. No pagination (inventory is small).

## 3. Approach

**On-demand parse at request time** (chosen). For each switch, read its
latest successful backup file and parse it live. No new storage of
parsed results.

Rejected: (B) parse-and-store at backup time — couples write path, adds
migration, premature; (C) scheduled static JSON export — stale data +
scheduler wiring.

**Performance:** the largest sample dump (274 KB WebSmart) parses in
<1 ms; disk read dominates. Hundreds of switches on the bulk endpoint
stay well under ~1–2 s. A `content_hash`-keyed cache (the column already
exists on `backups`) memoizes parsed docs; the hash changes only when
config changes, so the cache is self-invalidating. Single-switch
endpoint is always fast.

## 4. Architecture

### 4.1 Parser layer — `app_v4/net/config_parsers/`

Pure functions, no I/O, independently testable.

- `types.py` — dataclasses `SwitchDoc`, `VlanDoc`, `PortDoc`.
- `awplus.py` — AlliedWare Plus CLI parser.
- `dell.py` — Dell-style CLI parser (range replay).
- `websmart_snmp.py` — WebSmart / V2 SNMP-dump decoder.
- `__init__.py` — `parse_config(text: str) -> SwitchDoc`: detect dialect
  from content and dispatch.

**Dialect detection** (content-based, because both CLI dialects use
protocol `ssh`/`telnet`):
- contains `interface port1.0.` → AlliedWare Plus
- contains `interface ethernet g` or `interface range ethernet` → Dell
- starts with a model banner + `@` group markers / `1.3.6.1` OIDs → WebSmart
- otherwise → `SwitchDoc` with `parse_warnings=["unknown dialect"]` and
  empty vlans/ports (never raise).

### 4.2 Output shape (structured only)

```
SwitchDoc:
  switch_id: int
  name: str                # from DB switch record
  ip: str                  # from DB switch record
  protocol: str            # from DB switch record
  hostname: str | None     # parsed from config when present
  source_backup_id: int | None
  backup_taken_at: datetime | None
  vlans: list[VlanDoc]
  ports: list[PortDoc]
  parse_warnings: list[str]

VlanDoc:  { id: int, name: str | None }

PortDoc:
  name: str                # "port1.0.1" | "g1" | "1"
  description: str | None
  enabled: bool            # false if shutdown
  mode: "trunk" | "access" | "unknown"
  native_vlan: int | None      # trunk native / PVID
  access_vlan: int | None      # when mode == access
  trunk_allowed_vlans: list[int]
```

`ip`, `name`, `protocol` come from the DB `Switch` row (single source of
truth, consistent across dialects). The parser only fills config-derived
fields.

## 5. Per-dialect parsing rules

### 5.1 AlliedWare Plus (`awplus.py`)
- VLAN names from the `vlan database` block: `vlan <id> name <name>`.
  Expand ranges in `vlan 4-6,8-12 state enable` for the id set.
- Per `interface port1.0.N` block until next `!`:
  - `description X` → description (strip surrounding quotes).
  - `shutdown` → `enabled=false`.
  - `switchport mode trunk|access` → mode.
  - `switchport trunk native vlan N` → native_vlan.
  - `switchport trunk allowed vlan add <list>` → trunk_allowed_vlans
    (expand comma/range list e.g. `4-6,8-12,88`).
  - `switchport access vlan N` → access_vlan.

### 5.2 Dell-style (`dell.py`)
Config is applied cumulatively via `interface range ethernet g(...)`
blocks scattered through the file and in order. Replay:
- Maintain `ports: dict[str, PortDoc]` keyed by `gN`.
- On `interface ethernet gN` or `interface range ethernet g(<ranges>)`:
  set current target = expanded port list.
- Apply subsequent lines until `exit`/next interface to every current
  target port: `description`, `switchport mode trunk`,
  `switchport access vlan N` (→ access_vlan, mode access),
  `switchport trunk native vlan N` (→ native_vlan),
  `switchport trunk allowed vlan add N` (append to trunk_allowed_vlans).
- Range syntax `g(1-3,6,8-13,16)` → expand to individual port ids.
- VLAN names from `interface vlan N` / `name X` blocks.
- No explicit shutdown in sample → `enabled=true` default.

### 5.3 WebSmart / V2 SNMP dump (`websmart_snmp.py`)

Dump format: `@ <n> <base-oid>` lines set the current base OID; data
rows are `<flag>\t.<col>.<index>\t<type>\t[<len>]\t<value>`. The OID
suffix (`.<col>.<index>`) is appended to the base for the full OID.

Relevant OIDs (Q-BRIDGE-MIB):
- base `1.3.6.1.2.1.17.7.1.4.3.1` (dot1qVlanStaticTable):
  - col `.1.<vlan>` = static name (octet string)
  - col `.2.<vlan>` = egress ports bitmap (octet string)
  - col `.4.<vlan>` = untagged ports bitmap (octet string)
- base `1.3.6.1.2.1.17.7.1.4.5.1` (dot1qPortVlanTable):
  - col `.1.<port>` = PVID (integer)
- `1.3.6.1.2.1.1.5.0` = sysName → hostname
- ifAlias `1.3.6.1.2.1.31.1.1.1.18.<port>` = port description (when present)

**Binary octet-string recovery (the key risk, solved):** the backup is
saved as UTF-8 text but SNMP octet strings are binary. Recover original
bytes by reading the file as UTF-8 then `value.encode("latin-1")`
(lossless: the save was a 1:1 byte→codepoint decode). Do **not** take
"rest of line" as the value — slice **exactly the declared length**
bytes from the recovered byte stream after the length token. Validate
decoded length == declared length.

Verified on sample: VLAN 88 egress `ffffffffffff0000` → ports 1–48;
VLAN 23 egress `0000000040010000` → ports 34, 48.

**Bitmap decode:** 1 bit per port, MSB of byte 0 = port 1.

**Classification per port:**
- native/access vlan = PVID (integer, always reliable).
- member VLANs = VLANs whose egress bitmap has the port set.
- tagged-on = member AND not in that VLAN's untagged bitmap.
- `mode = access` if the port is untagged in exactly its PVID VLAN and
  tagged on none; else `mode = trunk` with `native_vlan = PVID` and
  `trunk_allowed_vlans = member VLANs`.
- **Fallback:** if any bitmap fails length validation, skip
  bitmap-derived membership for that record, set `mode="unknown"`, keep
  `native_vlan/access_vlan = PVID`, and append a `parse_warning`. PVID
  is unaffected, so native/access vlan is always reported.

## 6. API-key authentication

### 6.1 Model — `ApiKey` (`data/models.py`)
```
id: int pk
name: str unique            # human label
key_hash: str               # sha256 hex of the plaintext key
prefix: str                 # first 8 chars, for display only
created_at: datetime
last_used_at: datetime | None
revoked: bool = false
```
Table auto-created by `Base.metadata.create_all` (no Alembic; SQLite).

Plaintext key = `ncr_` + `secrets.token_urlsafe(32)`. Stored only as
sha256; returned in full **once** at creation.

### 6.2 Dependency — `require_api_key` (`service/deps.py`)
- Accept `Authorization: Bearer <key>` **or** `X-API-Key: <key>`.
- sha256 the presented key, look up a non-revoked row; 401 on miss.
- Update `last_used_at` (best-effort, non-blocking to the response).

### 6.3 Management endpoints — `service/api/api_keys.py`
Admin-only (`require_role("admin")`), prefix `/api/v1/api-keys`:
- `POST /` `{name}` → `{id, name, prefix, key}` (**key shown once**).
- `GET /` → list `{id, name, prefix, created_at, last_used_at, revoked}`.
- `DELETE /{id}` → revoke (soft: set `revoked=true`).
Audit `apikey.created` / `apikey.revoked` via existing audit writer.

### 6.4 Web UI (Settings section)
An "API Keys" section on the existing Settings page: create (shows the
key once with a copy button), list, revoke. Reuses existing hooks/types
patterns. *(Trimmable to backend-only if desired — not a blocker.)*

## 7. Documentation endpoints — `service/api/network_doc.py`

Prefix `/api/v1/network-doc`, auth `require_api_key`:
- `GET /` → `list[SwitchDoc]` for all active switches. Each switch: load
  latest successful backup via `repo.get_latest_backup`; if it has a
  `file_path`, read + `parse_config`, then overlay DB `ip/name/protocol`
  and backup id/timestamp. Switch with no successful backup → entry with
  `parse_warnings=["no successful backup"]`, empty vlans/ports.
- `GET /{switch_id}` → single `SwitchDoc`; 404 if switch missing.

Parsed results cached in a module-level `dict[content_hash, SwitchDoc-ish]`
(config-derived fields only; DB overlay applied per request).

## 8. Wiring & repository

- `data/models.py`: add `ApiKey`.
- `data/repository.py`: `create_api_key`, `list_api_keys`,
  `get_api_key_by_hash`, `revoke_api_key`, `touch_api_key_last_used`.
  (Reuse existing `get_latest_backup`, `list_switches`.)
- `service/app.py`: `include_router(api_keys.router, prefix="/api/v1")`
  and `include_router(network_doc.router, prefix="/api/v1")`.
- No DB migration needed beyond the auto-created table.

## 9. Error handling

- Parser functions never raise on malformed input; they return a
  partial `SwitchDoc` with `parse_warnings`. A single bad file must not
  fail the whole bulk response.
- Missing/unreadable backup file → warning, empty doc, HTTP 200.
- Auth failures → 401 (problem+json, consistent with existing handlers).

## 10. Testing

One `test_*.py` per parser, using the four sample files as fixtures:
- `test_parse_awplus.py` — assert VLAN table subset; assert a trunk port
  (port1.0.1: native 11, allowed [88]) and an access port (port1.0.6:
  access vlan 11); a shutdown port is `enabled=false`.
- `test_parse_dell.py` — assert range replay: `g7` access vlan 8,
  `g22-24` trunk with expected allowed set; VLAN name table subset.
- `test_parse_websmart.py` — assert VLAN names (88=IPH-DEVICE),
  egress decode (vlan 88 → all 48 ports; vlan 23 → {34,48}), PVID→port
  native/access; assert length-validation fallback path emits a warning.
- `test_api_keys.py` — create returns plaintext once; valid key passes
  `require_api_key`; revoked/absent → 401; admin-only on management.

No new test framework — extend the existing `app_v4/tests` pytest setup.

## 11. File change summary

New:
- `app_v4/net/config_parsers/{__init__,types,awplus,dell,websmart_snmp}.py`
- `app_v4/service/api/{api_keys,network_doc}.py`
- `app_v4/tests/{test_parse_awplus,test_parse_dell,test_parse_websmart,test_api_keys}.py`
- `app_v4/tests/test_network_doc_api.py`

Modified:
- `app_v4/data/models.py` (add `ApiKey`)
- `app_v4/data/repository.py` (api-key methods)
- `app_v4/service/deps.py` (`require_api_key`)
- `app_v4/service/app.py` (register two routers)
- Web: Settings page + `api/hooks.ts` + `api/types.ts` (API-key section)

## 12. Risks

- **WebSmart bitmap encoding** — solved via latin-1 recovery +
  length-field slicing + validation + PVID fallback (Section 5.3). PVID
  guarantees native/access vlan; trunk-allowed list is best-effort with
  a warning on any anomaly.
- **Dialect drift** — new firmware could change CLI/OID layout; detection
  falls back to a warning-only empty doc rather than a hard failure.
- **Bulk latency at large scale** — mitigated by the content_hash cache;
  parse cost is negligible, disk read is the floor.
