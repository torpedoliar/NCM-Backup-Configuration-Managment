# NCM v4 Production Completion — Design

**Date:** 2026-05-20
**Status:** Approved (brainstorming)
**Strategy:** Vertical slice per feature (Approach B). Each slice ships UI + backend + tests before next.

## Context

NCM v4 is a Windows desktop network configuration manager that backs up Allied Telesis switches. The PyInstaller build now starts cleanly (post 4.7-bug fixes), but four production gaps surfaced once the wizard was usable end-to-end:

1. Login page layout is broken (label-input alignment, no centered card).
2. Dashboard widgets show hardcoded mock data ("Twelve switches, three-forty-eight backups, one anomaly").
3. CRUD UI is missing for Switches, Credentials, Schedules, Users — backend endpoints exist but the SPA only reads.
4. Settings page is a placeholder ("Service, branding, retention, logs, about.") with no controls.

Six additional latent issues were discovered during exploration and added to scope:

5. Dashboard "buttons that don't work" — time-range tabs, EXPORT, sidebar counts.
6. History page lacks filters/actions; Diff page requires raw IDs.
7. No logout button anywhere; no audit log page despite backend `/audit` endpoint existing.
8. Wizard accepts any input (empty passphrase, port `0`, weak admin password).
9. Authentication policies (token lifetime, lockout, password rules) are hardcoded, not editable.
10. No log viewer; no log file at all currently — `SAFE_LOG_CONFIG` routes to `NullHandler`.

This spec covers all ten as one continuous workstream. Each section below is implementable independently and ships value.

---

## Section 1 — Login layout fix

**Goal:** Centered card 380px max-width, dark theme consistent, headline + form aligned.

### Changes

- `app_v4/web/src/auth/LoginPage.tsx` — wrap content in `.login-card` flex-centered (`min-height: 100vh`, `align-items: center`, `justify-content: center`).
- `app_v4/web/src/auth/login.css` (new) — styles for `.login-card`, `.login-form`, `.login-headline`, `.login-error`. Use existing tokens `--bg-0`, `--accent-amber`, `--text-1`, `--border-1`.
- Form: `flex-direction: column`, `gap: 16px`. Label above input, full-width input, `padding: 10px 14px`, focus border amber. Submit button full-width matching QSS button style.
- Error inline above submit, color `#ef4444`.

### Tests

- `LoginPage.test.tsx` — assert form is inside `.login-card`, fields stack vertically, submit button present.

### No backend change.

---

## Section 2 — Dashboard real data + working buttons

**Goal:** Every widget consumes API/WebSocket; every visible button has a handler.

### Changes

- `DashboardPage.tsx` — hero headline becomes dynamic from `useSystemMetrics()`. Skeleton when loading.
- `FleetGrid.tsx` — replace hardcoded array with `useSwitches()` + `useBackups()` per switch. Status logic: `ok` if last successful backup within 24h, `warn` >24h, `fail` if last backup failed.
- `LiveFeed.tsx` — drop hardcoded entries; subscribe to `useLiveSocket`. Maintain last 50 events in a Zustand store. Footer "{n} EVENTS / 24H" computed from store. "VIEW ALL" links to `/audit`.
- `BackupChart.tsx` — replace hardcoded with `useBackups()` bucketed per day client-side. Receives `range` prop.
- Time-range tabs in `DashboardPage.tsx` — convert to state, sync to URL `?range=7d` (Wouter supports). Pass to chart and to filtered metrics.
- EXPORT button — fetch `/backups?limit=10000&from_ts=…&to_ts=…` (filter params added in Section 5), convert to CSV (`switch_name,taken_at,success,size_bytes,backup_type,message`), trigger anchor download.
- `Sidebar.tsx` — switches/backups/jobs/users counts read from `useSystemMetrics()`. Loading state: `—`.

### Tests

- `DashboardPage.test.tsx` — extend: headline reflects mock metrics, range tabs change state, EXPORT triggers download.
- `FleetGrid.test.tsx` (new) — status derived from last backup of each switch.
- `LiveFeed.test.tsx` (new) — emit mock WebSocket event, appears in list.
- `Sidebar.test.tsx` (new) — counts dynamic.

### No backend change.

---

## Section 3 — CRUD Switch + Credential (inline, hybrid, soft delete)

**Goal:** Add/Edit/Deactivate/Delete switches and credentials directly from the table.

### Switch row UX

- `[+ Add switch]` header button → new editable row at top.
- Click row action menu → Edit / Deactivate (active) or Edit / Activate / Delete (inactive).
- Inactive switches: opacity 60%, "INACTIVE" badge.
- Toggle `[Show inactive]` filter in header; default off.

### Switch fields

| Column | Input | Validation |
|---|---|---|
| Name | text | required, unique, ≤100 |
| Host/IP | text | required, IPv4 or hostname |
| Protocol | select SSH/Telnet/WebSmart | required |
| Port | number | 1-65535, default by protocol |
| Credential | combo (existing + "+ New credential") | required |
| Notes | text | ≤500 |

### Hybrid credential combo

- Dropdown lists existing credentials by name + "+ New credential…" item.
- Selecting "+ New credential" expands inline sub-form: name, username, password, enable_password (optional). On save → POST `/credentials` first, then use returned ID for the switch.
- Edit mode: dropdown defaults to current credential; can re-select or create new.

### Soft delete (DB schema change)

- `Switch.is_active: bool = True` (new column, mirror `User.is_active`).
- `Switch.deactivated_at: datetime | None`.
- Migration via `_run_sqlite_migrations` (existing `_add_column_if_missing` pattern).

### Backend

- `PATCH /switches/{id}` accepts `is_active` field.
- `POST /switches/{id}/deactivate` (idempotent).
- `POST /switches/{id}/activate`.
- `DELETE /switches/{id}` returns 409 if `is_active=True`. Hard-deletes only deactivated switches.
- `GET /switches` filters `is_active=True` by default; `?include_inactive=true` for admin view.
- Scheduler `sync_once()` filters `is_active=True`.
- Manual backup via API on inactive switch returns 409.
- Audit: `switch.deactivated`, `switch.activated`, `switch.deleted`, `switch.created`, `switch.updated`.

### Credentials

- `CredentialsPage.tsx` — same inline pattern. Field: name + username + password + enable_password (write-only).
- Display: name + masked secret. Action: Edit / Delete.
- Delete blocked when `Credential.switches` non-empty (FK constraint surfaces as 409 with friendly message).
- Permissions: switch CRUD = admin/operator; credential CRUD = admin only.

### Tests

- Backend: deactivate/activate, delete-while-active 409, scheduler skips inactive, manual backup blocked.
- Frontend: SwitchesPage Add row → POST, Edit row → PATCH, Cancel reverts. Hybrid combo: select "+ New" expands sub-form, two sequential mutations on save. Inactive badge + filter.
- Frontend: CredentialsPage password not echoed back after save. Delete-in-use shows 409 message.

---

## Section 4 — CRUD Schedule + User (inline)

**Goal:** Manage backup jobs and users from the SPA.

### Schedules

`SchedulesPage.tsx` — same inline pattern.

| Column | Input | Validation |
|---|---|---|
| Switch | combo (active only) | required |
| Name | text (auto: `Backup {switch_name}`) | ≤100 |
| Type | radio Interval/Daily/Weekly/Monthly | required |
| Interval | number (Interval) | 1-1440 min |
| Time | time picker `HH:MM` (Daily/Weekly/Monthly) | required |
| Day of week | dropdown (Weekly) | mon-sun |
| Day of month | number (Monthly) | 1-31 |
| Enabled | toggle | default on |

Mapping to `Job` schema: existing `interval_minutes` retained; new columns `Job.day_of_week: str | None`, `Job.day_of_month: int | None`. `scheduler._build_trigger` reads these instead of hardcoded `"mon"` and `1`.

Action menu per row: Edit / Run now / Toggle enabled / Delete.

**New endpoint:** `POST /jobs/{id}/run` — admin/operator. Calls `runtime.backup_service.execute_backup(switch_id, backup_type="manual_schedule")`. Returns 202.

### Users

`UsersPage.tsx` — inline pattern.

| Column | Input | Validation |
|---|---|---|
| Username | text | unique, 3-64, regex `^[a-zA-Z][a-zA-Z0-9_-]*$` |
| Role | select admin/operator/viewer | required |
| Password | password (Add only) | per password policy |
| Active | toggle | default on |

Action: Edit / Reset password (modal) / Toggle Active / Delete (blocked if `id == current user.id`).

**New endpoint:** `POST /users/{id}/password` — admin only. Body `{password}`. Hash + store. Audit `user.password_reset_by_admin`.

### Audit

- `schedule.created/updated/deleted/run_now/enabled_toggled`
- `user.created/updated/deleted/activated/deactivated/password_reset_by_admin`

### Tests

- Backend: `POST /jobs/{id}/run` triggers `BackupService`, audit recorded.
- Backend: `POST /users/{id}/password` hashes new password, old password rejected.
- Backend: schema migration adds `day_of_week`, `day_of_month`; existing rows keep null.
- Backend: `_build_trigger` for weekly/`day_of_week="fri"` produces correct CronTrigger.
- Frontend: SchedulesPage Add, Run now, Toggle. UsersPage Add, Reset password modal, Toggle active, delete-self disabled.

---

## Section 5 — History + Diff polish

**Goal:** History becomes the day-to-day workflow tool; Diff is usable without knowing IDs.

### History

`HistoryPage.tsx` filter bar: switch dropdown, type (All/Manual/Automatic), state (All/Success/Failed), date range (default last 30d), search (in `message`). Filter encoded to query string.

Backend `GET /backups` extends with `success: bool | None`, `backup_type: str | None`, `from_ts`, `to_ts`, `q`. `Repository.list_backups` extended.

Table columns: Time (relative), Switch (link), Type (badge), State (badge), Size (KB), Message (truncated + tooltip), Actions.

Actions per row:
- **View** — modal showing full config from `GET /backups/{id}/content`. Copy button.
- **Download** — same endpoint with `?download=true`, sets `Content-Disposition: attachment; filename={switch}_{ts}.txt`.
- **Delete** — admin only. `DELETE /backups/{id}` removes DB row + file (`unlink(missing_ok=True)`). Audit `backup.deleted`.

### Diff

`DiffPage.tsx` replaces raw ID inputs with three pickers:

1. Switch dropdown (defaults to first switch with history).
2. Backup A picker (list of switch's backups, default penultimate).
3. Backup B picker (default latest).
4. Compare button (disabled until A ≠ B).

Permalink: `/diff?switch=12&a=348&b=349`.

Edge cases:
- Switch has no history → pickers disabled, "No history yet".
- Only 1 backup → message "Need at least 2 to compare".

### Tests

- Backend: `GET /backups` with each filter combination. `DELETE /backups/{id}` admin-only, file removed.
- Backend: content endpoint with `?download=true` includes `Content-Disposition`.
- Frontend: HistoryPage filter changes refetch with new params, View modal opens, Download triggers anchor click.
- Frontend: DiffPage pickers populate, Compare disabled when same.

---

## Section 6 — Logout button + Audit page

### Logout

- `Sidebar.tsx` adds `[Sign out ↗]` button next to admin indicator (bottom).
- Click: POST `/auth/logout` with refresh_token, `setAccessToken(null)`, clear `useAuth` store, `setLocation('/login')`. No confirm modal.
- `AuthProvider` adds `logout()` action invoking the four steps.
- `attachAuthInterceptor` `onUnauthorized` callback wired to `logout()` (auto-logout on 401).

### Audit

`AuditPage.tsx` (new) at `/audit`. Wouter route. Sidebar link in MONITORING group, hidden for non-admin.

Backend `GET /audit` extends with filters: `action: str | None` (prefix match), `user_id: int | None`, `from_ts`, `to_ts`, `offset: int = 0`. Response sets `X-Total-Count` header.

`Repository.list_audit` extended; `Repository.count_audit` new.

Columns: Time (relative), User (joined username or "system"), Action (badge with color group), Target (`{type}:{id}` link), IP, Detail (button → modal with formatted JSON).

Filter bar: action group dropdown (All/Auth/Switch/Credential/Schedule/User/Backup/System/Failed only), user dropdown, date range, search.

Pagination: "Load more" button (offset += limit).

### Tests

- Backend: filter combinations, pagination, `X-Total-Count` correct, non-admin 403.
- Frontend: AuditPage rendering, filter refetch, Load more, detail modal. Sidebar logout triggers `logout()`. Activity link admin-gated.

---

## Section 7 — Wizard input validation

**Goal:** Reject weak/invalid input at first run so installs don't leave easy-to-guess accounts.

### Validators (`desktop/setup/validators.py`, new — pure, no Qt)

```python
def validate_passphrase(value: str, confirm: str) -> str | None
def validate_username(value: str) -> str | None
def validate_password(value: str, confirm: str) -> str | None
def validate_bind_host(value: str) -> str | None
def validate_bind_port(value: str) -> str | None
```

Each returns `None` (valid) or error message string.

### Rules

- **Passphrase:** ≥12 chars, must include upper + lower + digit. Confirm field required, must match. Hint text: "You will need it to unlock backups after reinstall."
- **Username:** 3-64 chars, regex `^[a-zA-Z][a-zA-Z0-9_-]*$`.
- **Password:** ≥8 chars, upper + lower + digit. Confirm + match. (Wizard uses default policy because runtime policy isn't created until init completes — see Section 9.)
- **Bind host:** `127.0.0.1`, `0.0.0.0`, IPv4 dotted (each octet 0-255), or hostname. `0.0.0.0` shows warning helper text.
- **Bind port:** integer 1024-65535.

### Wizard pages

Each page overrides `isComplete()` returning `_validation_error() is None`. `textChanged` connects to `completeChanged.emit` plus updates a `QLabel#error` that turns red/empty.

Add `master_passphrase_confirm` and `password_confirm` fields. Add `error_label` per page.

### Tests

- `test_setup_validators.py` (new, no Qt) — covers each validator's pass/fail cases.
- `test_desktop_setup_config.py` extend — `isComplete()` False for invalid, True for valid; error labels update.

---

## Section 8 — Settings: Service / Retention / About

### Layout restructure

`SettingsPage.tsx` → vertical tabs on the left for: Service / Retention / Authentication / Logs / About. Wouter sub-route `/settings/:tab`. Default `/settings` redirects to `/settings/service`.

### 8a — Service

Read-only display from `/system/status`:

| Field | Source |
|---|---|
| Bind host / port | `host`, `port` |
| Status | `service` + indicator dot |
| Started at | formatted |
| Uptime | formatted |
| Version | `version` |

Action `[Restart service]` is **disabled with tooltip** "Restart not yet implemented; close and reopen the app." Proper restart deferred.

### 8b — Retention

Editable (admin only):

| Field | Range | Default |
|---|---|---|
| Backup minimum keep | ≥1 | 1 |
| Backup retention days | ≥7 | 365 |
| Audit retention days | ≥7 | 90 |
| Sweep hour | 0-23 | 3 |
| Sweep minute | 0-59 | 0 |

**Storage:** `data/runtime_settings.json` (new). Mirror pattern of `data/service.json`. `core/runtime_settings.py` (new) provides load/save/atomic-update helpers.

**Endpoints:**
- `GET /system/retention` — viewer+, returns current values.
- `PATCH /system/retention` — admin only, partial body, validates ranges, persists, hot-reloads `RetentionService`. APScheduler `reschedule_job` updates next run when sweep_hour/minute change.

**Audit:** `system.retention_updated` with diff.

### 8c — About

Read-only (extend `/system/status` with paths):

| Field | Source |
|---|---|
| Application name | hardcoded |
| Version | `app_v4.__version__` |
| Build date | env or hardcoded at build |
| Total switches/backups/jobs | `/system/metrics` |
| Failures (24h) | `/system/metrics` |
| DB size | `/system/status.db_size_bytes` |
| Backup storage path | `/system/status.backups_dir` (new) |
| Logs path | `/system/status.logs_dir` (new) |
| Data path | `/system/status.data_dir` (new) |

`StatusResponse` adds `data_dir`, `backups_dir`, `logs_dir` (str path).

### Tests

- Backend: `test_retention_settings_api.py` — GET, PATCH valid, PATCH invalid 422, PATCH non-admin 403, scheduler reschedules.
- Backend: `test_system_api.py` extend — paths fields.
- Frontend: each section component renders mock data, retention edit/save invalidates query.

---

## Section 9 — Settings: Authentication (Token / Lockout / Password policy)

### Storage

Extend `runtime_settings.json` with `auth` section:

```json
{
  "auth": {
    "access_token_minutes": 15,
    "refresh_token_days": 7,
    "lockout_threshold": 5,
    "lockout_window_minutes": 10,
    "lockout_duration_minutes": 30,
    "password_min_length": 8,
    "password_require_upper": true,
    "password_require_lower": true,
    "password_require_digit": true,
    "password_require_symbol": false
  }
}
```

### Endpoints

- `GET /system/auth-settings` — admin only, returns current.
- `PATCH /system/auth-settings` — admin only, partial body, validates ranges, persists.

### 9a — Token lifetime

| Field | Range | Default |
|---|---|---|
| Access token minutes | 5-1440 | 15 |
| Refresh token days | 1-30 | 7 |

`AuthService` reads runtime values at issue time (not constructor). Provider pattern:

```python
AuthSettingsProvider = Callable[[], AuthSettings]

class AuthService:
    def __init__(self, jwt_secret: bytes, settings_provider: AuthSettingsProvider): ...
    def issue_access_token(self, ...):
        minutes = self.settings_provider().access_token_minutes
        exp = now() + timedelta(minutes=minutes)
        ...
```

Provider is bound at runtime construction to a function reading from `runtime_settings.json` cache.

Audit: `system.auth_settings_updated`.

### 9b — Lockout

| Field | Range | Default |
|---|---|---|
| Failed attempts threshold | 0-20 (0=disabled) | 5 |
| Failure window (minutes) | 1-60 | 10 |
| Lockout duration (minutes) | 1-1440 | 30 |

**Schema:** `User.failed_login_count: int = 0`, `User.last_failed_login_at: datetime | None`, `User.locked_until: datetime | None`. Migration via `_run_sqlite_migrations`.

**Login flow (`api/auth.py:login`):**
1. Unknown user → audit `auth.login_failed_unknown_user`, 401.
2. `locked_until > now()` → audit `auth.login_blocked_locked`, 423 Locked.
3. Failed password verify → if `last_failed_login_at` outside window, reset counter; increment; if counter >= threshold and threshold > 0, set `locked_until = now() + duration`, audit `auth.locked`. Audit `auth.login_failed`. 401.
4. Success → reset counter, `last_failed_login_at`, `locked_until` to null/0.

Threshold 0 disables lockout entirely.

**Endpoint:** `POST /users/{id}/unlock` — admin clears lock fields. Audit `user.unlock_by_admin`.

### 9c — Password policy

| Field | Default |
|---|---|
| Min length | 8 (range 6-128) |
| Require uppercase | true |
| Require lowercase | true |
| Require digit | true |
| Require symbol | false |

`core/password_policy.py` (new) — pure validator returning error message or `None`.

Applied at:
- `cli init_command` admin user creation (uses defaults at first init).
- `users.create_user` API.
- `users.{id}/password` reset API.
- Wizard AdminPage uses default policy (runtime not yet available pre-init).

Backend returns 422 ProblemDetail with field-level message.

### UI

`SettingsAuthSection.tsx` — three sub-cards (Token Lifetime / Account Lockout / Password Policy) within the "Authentication" tab. Each has its own [Save] button + dirty indicator.

### Tests

- `test_password_policy.py` (new) — pure unit tests for all combinations.
- `test_auth_settings_api.py` (new) — GET/PATCH admin, range validation, non-admin 403.
- `test_auth_lockout.py` (new) — threshold, window expiry resets counter, success resets, threshold=0 disabled, locked status returns 423.
- `test_auth_token_lifetime.py` (new) — PATCH access minutes, exp claim of issued token reflects new value.
- Frontend: `SettingsAuthSection.test.tsx`.

---

## Section 10 — Settings: Logs (file logger + viewer)

### Backend file logger

`core/logging.py` (new):

```python
def configure_file_logger(logs_dir: Path) -> None:
    log_file = logs_dir / "ncm-v4.log"
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5,
                                  encoding="utf-8")
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
```

Called from `desktop/main.py:main()` after `_resource_base_dir()` resolves; also from `service/main.py:main()` for standalone service mode.

`SAFE_LOG_CONFIG` in `desktop/launcher.py` updated to route uvicorn handlers to `RotatingFileHandler` instead of `NullHandler` (still avoids `DefaultFormatter.isatty()`). File path resolved via `os.environ["NCM_V4_BASE_DIR"]` (set in `desktop/main.py:main()`).

### Endpoint

`GET /system/logs` — admin only.

Query params: `lines: int = 200` (max 5000), `level: str | None`, `q: str | None`, `since: datetime | None`.

Response:
```json
{
  "lines": [
    {"ts": "2026-05-20 09:43:21", "level": "INFO", "logger": "uvicorn.error", "message": "..."}
  ],
  "total_returned": 100,
  "log_file": "logs/ncm-v4.log",
  "log_file_size_bytes": 12345
}
```

Implementation: efficient seek-from-end tail (chunk-by-chunk reverse read), regex-parse each line by configured format pattern, apply filter, return last `lines`.

Audit: `system.logs_viewed`.

### UI

`SettingsLogsSection.tsx`: level dropdown, search, refresh, auto-refresh toggle (5s polling when on), `<pre>` block with color-by-level, "Load 200 more" up to 5000 cap.

### Tests

- `test_system_logs_api.py` (new) — no filter, level filter, search, missing file, non-admin 403, performance with 100K lines under 500ms.
- `test_logging_setup.py` (new) — handler attached, log emitted ends in file, rotation triggers after maxBytes.
- Frontend: `SettingsLogsSection.test.tsx`.

### Risks & mitigations

- **File lock on Windows**: reader closes handle quickly; rotation handled by `RotatingFileHandler` with its own locking.
- **PII**: confirm passwords never logged (current code doesn't); `system.logs_viewed` audit gives trail of who saw what.
- **Performance**: tail via reverse-read chunks, hard timeout 5s returns partial with warning.

---

## Cross-cutting decisions

- **Storage choice:** `data/runtime_settings.json` for editable runtime config (retention, auth). Pydantic `Settings` becomes startup default + env override; runtime values override at read time.
- **Backwards compatibility:** all schema additions use `_run_sqlite_migrations` `_add_column_if_missing` pattern — existing DBs upgrade in place.
- **Audit coverage:** every mutation surfaced in this design records audit events. Naming convention `{domain}.{verb}` already used.
- **Permission gate:** admin-only for credential CRUD, user CRUD, retention/auth/logs settings, audit page, backup delete, restart action. Operator can: switch CRUD, schedule CRUD, run backup. Viewer can: read everything except settings/audit/logs.

## Out of scope (deferred)

- Service restart action implementation (button stays disabled with tooltip).
- TLS/HTTPS support for backend (still HTTP loopback).
- Code signing the exe.
- Translation/i18n (English only).
- Soft delete for users, schedules, backups (only switches get soft delete this round).

## Implementation order (vertical slices)

1. Section 1 — Login layout (frontend only, ~1h).
2. Section 2 — Dashboard real data (frontend only, ~3h).
3. Section 3 — Switch + Credential CRUD with soft delete (frontend + backend schema, ~6h).
4. Section 4 — Schedule + User CRUD (frontend + backend schema + new endpoints, ~5h).
5. Section 5 — History + Diff polish (frontend + backend filter extension, ~4h).
6. Section 6 — Logout + Audit page (frontend + backend filter extension, ~3h).
7. Section 7 — Wizard validation (desktop + new validators module, ~2h).
8. Section 8 — Settings Service/Retention/About (frontend + backend retention API + JSON storage, ~4h).
9. Section 9 — Settings Auth (frontend + backend auth-settings + lockout middleware + schema, ~6h).
10. Section 10 — Settings Logs (frontend + backend file logger + tail endpoint, ~3h).

Total estimate: ~37 hours of focused work across sessions.
