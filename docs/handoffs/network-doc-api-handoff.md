# Handoff: Network Documentation API — Implementation

**Date:** 2026-08-18
**Status:** MERGED to `main` (commit `c95fde6`), 270 tests passing
**Previous worker:** Claude Code (subagent-driven development, 19 commits with per-task review)
**This document:** context for the next agent continuing this work

## What was built

A read-only FastAPI API that exposes the latest **successful** backup of every switch as structured JSON, so an external network-documentation application can consume per-switch IP, port config, trunk/access status, and VLAN assignment (native vlan, trunk-allowed vlans, access vlan) plus the VLAN name table.

**Endpoints:**
- `GET /api/v1/network-doc` — all active switches, structured docs
- `GET /api/v1/network-doc/{switch_id}` — one switch; 404 if missing
- `POST /api/v1/api-keys` — admin-only; creates a key, returns plaintext ONCE
- `GET /api/v1/api-keys` — admin-only; lists name/prefix/created/last_used/revoked (never the key)
- `DELETE /api/v1/api-keys/{key_id}` — admin-only; soft-revokes

**Auth:** named, revocable API keys. Plaintext = `ncr_` + `secrets.token_urlsafe(32)`, stored ONLY as SHA-256 hex digest. Present as `Authorization: Bearer <key>` OR `X-API-Key: <key>`. Admin endpoints use the existing JWT `require_role("admin")`, NOT API keys.

**Parser layer** (`app_v4/net/config_parsers/`, pure functions, no I/O, never raise):
- `awplus.py` — AlliedWare Plus CLI (`interface port1.0.N` blocks)
- `dell.py` — Dell-style CLI, cumulative `interface range ethernet g(...)` replay
- `websmart_snmp.py` — WebSmart/V2 SNMP MIB dump; binary octet strings recovered via `latin-1` round-trip + length-exact slicing (NOT "rest of line")
- `__init__.py` — `parse_config(text)` + `detect_dialect(text)`; detection is CONTENT-based because both CLI dialects share protocol `ssh`/`telnet` in the DB

**Output shape** (`SwitchDoc`): `switch_id, name, ip, protocol` (from DB switch row), `hostname, vlans[{id,name}], ports[{name, description, enabled, mode, native_vlan, access_vlan, trunk_allowed_vlans}], source_backup_id, backup_taken_at (UTC-aware), parse_warnings`. Config-derived fields only from parser; identity always from DB.

## Key decisions / design notes

- **On-demand parse at request time** (chosen) vs parse-at-backup-time (rejected) vs scheduled export (rejected). Largest sample (274 KB WebSmart) parses in <1 ms.
- **`content_hash`-keyed cache** in `network_doc.py` (`_PARSE_CACHE` dict) memoizes `ParsedConfig`; DB identity overlaid per request. Self-invalidating because hash changes only when config changes. NOT thread-safe (race is a wasted parse; acceptable).
- **Per-switch error containment**: one unreadable/malformed/missing backup produces HTTP 200 + a doc with `parse_warnings` — never breaks the bulk response.
- **Never-raise invariant** is held by convention across all parsers (guarded `int()` via `_vlan_id`/`_int_or_warn`; `expand_id_list` is lenient). Deliberately NO `try/except` at the `parse_config` boundary — that would mask real parser bugs; the request-level guard lives in the network_doc router.

## How to run / test

- Tests: `py -3.13 -m pytest app_v4/tests -q` (270 passing). Bare `python` on this machine is 3.14 WITHOUT pytest; always use `py -3.13`.
- Test fixtures: `app_v4/tests/fixtures/network_doc/{awplus,dell,websmart,websmart_v2}.txt` — copied byte-for-byte from `Sample Backup/` (gitignored, exists only in the main checkout).
- To try it live: start the app, login admin, create a key via POST, then `curl -H "X-API-Key: <key>" http://localhost:<port>/api/v1/network-doc`.

## Files created/changed

**New:**
- `app_v4/net/config_parsers/{__init__,types,_common,awplus,dell,websmart_snmp}.py`
- `app_v4/service/api/{api_keys,network_doc}.py`
- `app_v4/service/timeutil.py` — `to_aware_utc` (also used by system.py; part of a base repair)
- `app_v4/tests/fixtures/network_doc/*.txt` (4)
- `app_v4/tests/test_parse_{common,awplus,dell,websmart,dispatch}.py`
- `app_v4/tests/test_{repository_api_keys,require_api_key,api_keys,network_doc_api}.py`
- `docs/superpowers/specs/2026-08-17-network-doc-api-design.md`
- `docs/superpowers/plans/2026-08-17-network-doc-api.md`

**Modified:**
- `app_v4/data/models.py` — added `ApiKey` table (auto-created via `Base.metadata.create_all`, NO Alembic, no migration)
- `app_v4/data/repository.py` — api-key methods (create/list/get_by_name/get_by_hash/revoke/touch)
- `app_v4/service/deps.py` — `require_api_key`
- `app_v4/service/app.py` — registered `api_keys` and `network_doc` routers

## Base repair included (important context)

Commit `5eeda0d` on main was **broken**: `system.py` imported `BackupLocationSettings` and the desktop theme exported `load_theme_qss`, but neither existed in committed files — they lived only in the user's uncommitted working tree. This broke `create_app()` and 65 API-layer tests. A repair commit (`ac23d91` on the feature branch, now merged) completed those changes: added `BackupLocationSettings` to `runtime_settings.py`, created `timeutil.py`, fixed the theme export. This is why `main` now has a merge commit `c95fde6` (a fast-forward plus an app.py conflict resolution).

## Known deferred items (non-blocking, triaged by final review)

- **Deprecation warnings**: ~480 across the suite from legacy `datetime.utcnow()` (models, repository, auth, events, scheduler). Pre-existing project-wide pattern; new code follows the convention deliberately. NOT a merge blocker but worth a dedicated cleanup pass.
- **AWPlus `_vlan_id` duplication**: same guarded-int helper duplicated in `awplus.py` and `dell.py` with slightly different signatures. Hoist to `_common.py` — but note Task 4's WebSmart parser uses a different `_int_or_warn` shape, so reconcile all three.
- **WebSmart fallback is VLAN-granular**: a port is demoted to `mode="unknown"` if ANY member VLAN has an unreadable untagged bitmap, even when another VLAN would independently prove it a trunk. Errs toward silence over a false assertion. Costs nothing on real fixtures.
- **`_hostname` in `websmart_snmp.py`**: parses its declared length with a bare `int()` and slices without the negative guard `_octets` has. Asymmetric; negative sysname length would silently truncate hostname (unreachable from real dumps).
- **Awplus marker in `__init__.py`**: hardcodes `port1.0.` while the parser regex accepts any `port<d>.<d>.<d>` triple. A second stack member or chassis config (port1.1.1, port2.0.1) parses correctly but detects as unknown.
- **`test_parse_common.py:20-21`**: `test_expand_id_list_tolerates_tabs_and_newlines` cannot fail (int() strips whitespace itself).
- **`test_parse_dell.py:43-49`**: `g23.description is None` is vacuous — passes under the mutation it claims to catch. The g20 assertion carries the real mutation sensitivity.
- **`X-API-Key` whitespace-only**: reaches SHA-256 lookup before returning 401, unlike whitespace Bearer which is rejected as missing pre-hash. Externally identical 401, no bypass. Now actually stripped in the fix wave (verify current state).

## Natural next steps (for the next agent)

1. **Optional Task 10**: Settings web UI "API Keys" section (create shows plaintext once with copy button, list, revoke). Backend fully usable without it; keys can be created via curl. The spec marks this optional.
2. **Cleanup pass**: modernize `datetime.utcnow()` → `datetime.now(timezone.utc)` project-wide; the fix wave already introduced `timeutil.to_aware_utc` as a pattern.
3. **Deferred refactor**: hoist `_vlan_id`/`_int_or_warn` into `_common.py`.
4. **Consumer documentation**: the spec (`docs/superpowers/specs/2026-08-17-network-doc-api-design.md`) has the full JSON shape and per-dialect rules if the external app needs a reference.
5. If `main`'s remaining ~60 uncommitted WIP files are meant to ship, they need their own commit/review before anything depends on them.

## Known limitations

- No historical/diff endpoints on the network-doc API (already exist elsewhere); no pagination (inventory is small); no config push; no parse-at-backup-time storage. All deliberate YAGNI per spec.
- `_PARSE_CACHE` is an unbounded process-lifetime dict; parsing is synchronous in an async endpoint. Fine at current inventory scale.
