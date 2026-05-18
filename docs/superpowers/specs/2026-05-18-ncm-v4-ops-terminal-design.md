---
name: ncm-v4-ops-terminal-design
description: Design spec for NCM v4.0 — full overhaul to client-server architecture with PySide6 desktop, React web client, and FastAPI backend service, all unified by the "Ops Terminal" design language.
metadata:
  type: spec
  topic: ui-rework
  date: 2026-05-18
---

# NCM v4.0 — "Ops Terminal" Overhaul

> Design language: **Refined brutalism, terminal-inspired.** Deep ink, bone, radar amber. JetBrains Mono + Geist Sans + Instrument Serif italic. Sharp corners. Marker codes. Dashed dividers. Editorial headlines instead of cold dashboard labels.

## 1. Goals & Non-Goals

### Goals
- **Visual overhaul**: replace generic ttkbootstrap aesthetic with a distinctive "Ops Terminal" design language applied consistently across desktop and web clients.
- **Workflow overhaul**: redesign navigation, IA, and high-frequency operations (backup, diff, schedule) for fewer clicks and clearer state.
- **Architectural overhaul**: split monolithic single-process desktop app into `service / desktop client / web client` so backups run 24/7 independent of user sessions, and remote teams can monitor & manage from any browser.
- **Code quality**: break down 113 KB / 54 KB / 49 KB single-file views into focused, testable modules.

### Non-Goals
- Not migrating off Python on the backend.
- Not changing the underlying network protocols (SSH/Telnet/WebSmart/WebSmart V2) — those are stable.
- Not changing the encryption primitives (Fernet AES-128 / PBKDF2-HMAC-SHA256). Master passphrase storage gets DPAPI added on top, but the credential encryption stays.
- Not supporting platforms other than Windows for the service (clients can be cross-platform but service is Windows-only).

## 2. Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│                  NCM Windows Service (24/7)                     │
│  ──────────────────────────────────────────────────────────────│
│   FastAPI app  │  WebSocket hub  │  Static web bundle server   │
│   APScheduler  │  Backup engine  │  Auth (JWT)                 │
│   ─────────────┴─────────────────┴───────────────────────────  │
│                  CryptoService (in-memory key)                 │
│   master passphrase ◀── DPAPI-decrypt at startup ── disk file  │
│   ─────────────────────────────────────────────────────────────│
│   SQLite DB (existing schema + new tables: users, sessions,    │
│              audit_log) via SQLAlchemy                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │ REST + WebSocket (HTTPS preferred)
                       │
        ┌──────────────┼──────────────┐
        │                             │
┌───────────────────┐         ┌──────────────────┐
│  Desktop Client   │         │   Web Client     │
│  (PySide6 + Qt)   │         │  (React + Vite)  │
│  Native shell +   │         │  Served by the   │
│  QWebEngineView   │         │  service itself  │
│  for visual-heavy │         │  on bind addr    │
│  panels           │         │  (e.g. :8443)    │
└───────────────────┘         └──────────────────┘
```

The migration strategy is **big bang in a new folder** (`app_v4/`). The existing `app/` stays untouched on `main` and continues to ship as v3.5.x. v4 develops in parallel until ready.

## 3. Decisions

| # | Aspect | Decision |
|---|---|---|
| 1 | Target version | NCM **v4.0.0** (major bump — breaking architecture change) |
| 2 | Backend stack | **FastAPI** + SQLAlchemy (reuse models) + APScheduler + Uvicorn |
| 3 | Realtime channel | **WebSocket** for live activity feed and job status |
| 4 | Auth | **JWT** (access + refresh) over HTTPS; argon2id for password hashing |
| 5 | RBAC | Three roles: **Admin, Operator, Viewer** |
| 6 | Master passphrase | Stored on disk **encrypted with Windows DPAPI** (CurrentUser scope of the service account); decrypted into memory at service startup |
| 7 | First-run setup | Setup wizard (run once at install) creates master passphrase + first admin user |
| 8 | Desktop stack | **PySide6** (Qt) shell with **QWebEngineView** for visual-heavy panels; QWebChannel bridge for native ↔ web ops |
| 9 | Web stack | **React 18 + Vite + TanStack Query + Recharts**, served as static bundle by the FastAPI service |
| 10 | Design language | **"Ops Terminal"** (see §10) |
| 11 | Migration strategy | **Big bang in new folder** (`app_v4/`); existing `app/` stays unchanged |
| 12 | Service hosting | Windows Service (existing `windows_service.py` infrastructure adapted) |

## 4. Project Structure

```
Test Project/
├── app/                          # v3.5.x — UNCHANGED. Ships as legacy.
├── app_v4/                       # NEW. v4.0 codebase.
│   ├── service/                  # Windows Service entry + FastAPI app
│   │   ├── main.py               # uvicorn entry
│   │   ├── windows_service.py    # SCM wrapper
│   │   ├── api/                  # FastAPI routers
│   │   │   ├── auth.py           # /api/auth/login, /refresh, /logout
│   │   │   ├── switches.py       # /api/switches CRUD
│   │   │   ├── credentials.py    # /api/credentials CRUD (encrypted)
│   │   │   ├── backups.py        # /api/backups list, /api/backups/{id}/run
│   │   │   ├── jobs.py           # /api/jobs CRUD + enable/disable
│   │   │   ├── users.py          # /api/users CRUD (admin only)
│   │   │   ├── system.py         # /api/system/status, /metrics
│   │   │   └── ws.py             # /ws live activity stream
│   │   ├── deps/                 # FastAPI dependency injection
│   │   │   ├── auth_dep.py       # require_role(Admin|Operator|Viewer)
│   │   │   └── crypto_dep.py     # get_crypto_service
│   │   └── static/               # Built web bundle (Vite dist/) is mounted here
│   ├── core/                     # Backend business logic (was services/)
│   │   ├── backup_service.py     # Refactored from app/services/backup_service.py
│   │   ├── crypto_service.py     # + DPAPI envelope for master passphrase
│   │   ├── schedule_service.py
│   │   ├── retention_service.py
│   │   ├── diff_service.py
│   │   ├── auth_service.py       # NEW: argon2id, JWT, sessions
│   │   └── audit_service.py      # NEW: write to audit_log table
│   ├── data/                     # DB layer
│   │   ├── db.py                 # Async SQLAlchemy engine
│   │   ├── models.py             # Existing entities + User, Session, AuditLog
│   │   └── repository.py         # Async repository
│   ├── net/                      # UNCHANGED from v3 (paramiko/telnet/websmart)
│   ├── desktop/                  # PySide6 desktop client
│   │   ├── main.py               # Qt entry
│   │   ├── shell/                # Native chrome
│   │   │   ├── main_window.py    # QMainWindow with sidebar + content area
│   │   │   ├── sidebar.py        # Custom sidebar widget (Ops Terminal style)
│   │   │   └── topbar.py         # Breadcrumb + service pulse + timecode
│   │   ├── views/                # One file per view, all <300 LOC
│   │   │   ├── dashboard_view.py # Hosts QWebEngineView with /dashboard
│   │   │   ├── inventory_view.py # Native QTableView (forms benefit from native)
│   │   │   ├── credentials_view.py
│   │   │   ├── history_view.py   # QWebEngineView for diff
│   │   │   ├── diff_view.py      # QWebEngineView (uses Monaco-like)
│   │   │   ├── schedules_view.py
│   │   │   ├── users_view.py     # NEW: admin manages users
│   │   │   └── settings_view.py  # Broken out from 113 KB monolith into tabs
│   │   ├── bridge/               # QWebChannel bridge (native ↔ web)
│   │   ├── api_client.py         # Talks to local service (http://127.0.0.1:8443)
│   │   └── theme/                # QSS stylesheets implementing Ops Terminal
│   └── web/                      # React web client
│       ├── package.json          # Vite + React 18 + TanStack Query + Recharts
│       ├── src/
│       │   ├── main.tsx
│       │   ├── api/              # API client (axios) + TanStack Query hooks
│       │   ├── auth/             # Login page, AuthContext, ProtectedRoute
│       │   ├── layout/           # Sidebar, Topbar, Shell (Ops Terminal)
│       │   ├── pages/            # Dashboard, Switches, Credentials, History, Diff, Schedules, Users, Settings
│       │   ├── components/       # KPI, Sparkline, FleetGrid, LiveFeed, etc.
│       │   ├── styles/           # CSS variables + tokens (single source of truth)
│       │   └── lib/              # ws.ts, fmt.ts, etc.
│       └── vite.config.ts
├── docs/superpowers/specs/
│   └── 2026-05-18-ncm-v4-ops-terminal-design.md   # this file
└── installer/                    # NEW: WiX/Inno Setup scripts for v4 installer
```

`app_v4/` ships as a single package. The Windows Service entry runs uvicorn on a configurable bind address (default `127.0.0.1:8443` for local-only; admin can change in setup wizard or settings). The web bundle is built at install time and served by FastAPI as static files plus an HTML5 history fallback.

## 5. Backend Service

### 5.1 Service lifecycle

1. **Boot (Windows starts)** → SCM starts the NCM service.
2. **Read DPAPI envelope** at `data/master.dpapi` → decrypt with CurrentUser scope of service account → master passphrase + JWT signing key in memory.
3. **Init `CryptoService`** with master passphrase → derived key resident in memory (never written to disk).
4. **Init DB** (SQLAlchemy async engine, SQLite WAL).
5. **Start `ScheduleService`** + `RetentionService`.
6. **Start uvicorn** with FastAPI app bound to the configured address (default `127.0.0.1:8443`).
7. Service stays up. SCM stop → graceful shutdown of scheduler, then uvicorn, then DB.

If DPAPI decrypt fails (service account changed, machine identity changed) — service logs `MASTER_KEY_UNAVAILABLE` and refuses to start. Admin must re-run the setup wizard from the desktop client.

### 5.2 API surface

REST endpoints under `/api/v1/`. WebSocket at `/ws`.

```
POST   /api/v1/auth/login                       # username + password → JWT pair
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout

GET    /api/v1/system/status                    # service uptime, scheduler state, DB size
GET    /api/v1/system/metrics                   # KPI numbers (auto-refreshed by clients)

GET    /api/v1/switches
POST   /api/v1/switches                         # admin/operator
GET    /api/v1/switches/{id}
PATCH  /api/v1/switches/{id}                    # admin/operator
DELETE /api/v1/switches/{id}                    # admin
POST   /api/v1/switches/{id}/backup             # trigger manual backup (operator+)

GET    /api/v1/credentials
POST   /api/v1/credentials                      # admin/operator (encrypted server-side)
PATCH  /api/v1/credentials/{id}
DELETE /api/v1/credentials/{id}

GET    /api/v1/backups?switch_id=&since=&limit=
GET    /api/v1/backups/{id}/content             # raw config text
GET    /api/v1/backups/diff?a=&b=               # unified diff between two backup IDs

GET    /api/v1/jobs
POST   /api/v1/jobs
PATCH  /api/v1/jobs/{id}
DELETE /api/v1/jobs/{id}

GET    /api/v1/users                            # admin only
POST   /api/v1/users                            # admin only
PATCH  /api/v1/users/{id}                       # admin only (or self for password)
DELETE /api/v1/users/{id}                      # admin only
GET    /api/v1/audit                            # admin only

WS     /ws                                      # subscribe to events: backup_started, backup_completed, backup_failed, job_triggered, audit
```

### 5.3 Auth & RBAC

- **Password hashing**: argon2id (memlimit 64 MB, opslimit 3 — tuned for service-class hardware).
- **Tokens**: JWT access (15 min) + refresh (7 days) signed with HS256. The signing key is a 32-byte random value generated at install time and stored in the same DPAPI envelope as the master passphrase (separate field). It is independent of the master passphrase, so a passphrase rotation does **not** invalidate sessions. Rotating the JWT key is an explicit admin action that revokes all sessions.
- **Roles** are stored on the `users` table and embedded in the JWT claims. FastAPI dependency `require_role()` gates each endpoint.

| Capability | Admin | Operator | Viewer |
|---|---|---|---|
| View dashboard, history, diffs | ✓ | ✓ | ✓ |
| Trigger manual backup | ✓ | ✓ | — |
| Add/edit/delete switches & credentials | ✓ | ✓ | — |
| Add/edit/delete schedules | ✓ | ✓ | — |
| Manage users | ✓ | — | — |
| Change system settings | ✓ | — | — |
| View audit log | ✓ | — | — |

### 5.4 New DB tables

```python
class User(Base):
    id, username (unique), password_hash, role (admin|operator|viewer),
    is_active, created_at, last_login_at

class Session(Base):
    id, user_id, refresh_token_hash, ip, user_agent, created_at, expires_at, revoked

class AuditLog(Base):
    id, user_id, action, target_type, target_id, ip, ts, detail_json
```

The existing `Credential`, `Switch`, `Backup`, `Job` tables stay — we extend `Backup` with `triggered_by_user_id` (nullable, NULL when scheduler triggered).

### 5.5 Master passphrase via DPAPI

`crypto_service.py` adds two helpers around the existing Fernet logic:

```python
def store_master_passphrase(passphrase: str) -> None:
    """Encrypt with DPAPI CurrentUser scope and write data/master.dpapi."""
    blob = win32crypt.CryptProtectData(
        passphrase.encode("utf-8"),
        "ncm-master-passphrase",     # description
        None, None, None,
        CRYPTPROTECT_UI_FORBIDDEN,
    )
    Path("data/master.dpapi").write_bytes(blob)

def load_master_passphrase() -> str:
    blob = Path("data/master.dpapi").read_bytes()
    _desc, plaintext = win32crypt.CryptUnprotectData(
        blob, None, None, None, CRYPTPROTECT_UI_FORBIDDEN
    )
    return plaintext.decode("utf-8")
```

The existing `.gui_passphrase` (XOR) and `.service_passphrase` (plaintext) files become obsolete — setup wizard migrates them by reading the value, calling `store_master_passphrase`, and deleting the legacy files.

## 6. Desktop Client (PySide6)

A native Qt shell that **looks the same as the web client** by sharing tokens and CSS-equivalent QSS. Visual-heavy panels (Dashboard, Diff Viewer, Backup History timeline) embed the same React components via QWebEngineView so we don't fork visualizations. Forms (Inventory, Credentials, Schedules, Settings) use native Qt widgets where input ergonomics matter.

### 6.1 Why hybrid (Qt + WebEngine)?

- **Native forms** = better input handling, native dialogs, instant validation, no bridge latency.
- **WebEngine for charts** = reuse Recharts/SVG components from the web client; no need to re-implement charting in Qt.
- **Single design language enforced** by sharing CSS tokens (translated to QSS via a small generator).

### 6.2 Shell layout

Mirrors the web shell exactly:

- 240 px sidebar (groups: Monitoring / Management / Administration) with brand block, blinking cursor caret, version tag, operator card at the footer.
- Topbar: breadcrumb (`monitoring / Dashboard`), service pulse, UTC offset + timecode.
- Content area scales to window.

### 6.3 Communication

- Talks to local service on `127.0.0.1:<port>` via `httpx.AsyncClient`. Same JWT flow as web.
- WebSocket subscription for live feed, identical to the web client.

### 6.4 Setup wizard

The desktop client is the **only** way to run the install wizard:

1. Welcome screen.
2. Pick service install path + bind address (loopback by default; advanced toggle exposes LAN bind + cert path).
3. Set master passphrase (and confirm).
4. Create first admin user.
5. **HTTPS cert**: by default the wizard generates a self-signed cert valid for 5 years (CN = machine hostname, SAN includes `localhost` + machine name + LAN IP at install time). Advanced toggle lets admin import an existing PFX. The web client and desktop client both pin the cert fingerprint after first connect.
6. Install Windows Service.
7. Done — launch dashboard.

After setup, the wizard is hidden. Re-running shows a re-configuration mode that requires admin login.

## 7. Web Client (React)

### 7.1 Stack

- **React 18 + TypeScript**, Vite as bundler.
- **TanStack Query v5** for server state.
- **Wouter** for routing (lighter than React Router; this app has flat navigation and doesn't need React Router's data APIs).
- **Recharts** for charts (sparklines + the bar chart on Dashboard); inline SVG for fleet grid (no library).
- **Zustand** for tiny UI state (sidebar collapsed, theme variant).
- **CSS variables + plain CSS modules** — no Tailwind, no UI kit. The Ops Terminal aesthetic is bespoke and a utility framework would dilute it.

### 7.2 Pages

| Path | Component | Notes |
|---|---|---|
| `/login` | `LoginPage` | Single password + username field. Editorial headline. |
| `/` | `DashboardPage` | KPIs, 14-day chart, live feed, fleet grid (matches mockup). |
| `/switches` | `SwitchesPage` | List + drawer-style detail (slide in from right). |
| `/credentials` | `CredentialsPage` | List; password field is write-only. |
| `/history` | `HistoryPage` | Per-switch timeline; clicking opens diff. |
| `/diff` | `DiffPage` | Picker + side-by-side or unified diff (Monaco editor in read-only mode). |
| `/schedules` | `SchedulesPage` | Per-switch jobs with interval picker (15m/1h/6h/12h/24h or custom hour). |
| `/users` | `UsersPage` | Admin only. |
| `/settings` | `SettingsPage` | Broken into focused tabs (Service, Branding, Retention, Logs, About). |

### 7.3 Realtime feed

Single `useWebSocket()` hook owned by a global `LiveActivityProvider`. Posts events to a Zustand store. The dashboard live feed and the topbar pulse both read from this store, so events surface instantly across the app.

## 8. Data Flow Examples

### 8.1 Manual backup from the web client

1. User clicks "Backup now" on a switch row.
2. Web client → `POST /api/v1/switches/{id}/backup` (JWT in header).
3. FastAPI checks role (Operator+), enqueues into `BackupService` worker.
4. Service WS broadcasts `backup_started` event with `{switch_id, switch_name, ts}`.
5. Worker connects via SSH/Telnet/WebSmart, fetches config, hashes, saves file, inserts `Backup` row.
6. Service WS broadcasts `backup_completed` (or `backup_failed` with reason).
7. All clients update KPIs and live feed.

### 8.2 Scheduled backup at 02:00

1. APScheduler triggers job inside the service. No clients needed.
2. Same backup path as above. WS broadcast goes out — anyone listening sees it.
3. Backup row inserted with `backup_type='automatic'` and `triggered_by_user_id=NULL`.

## 9. Error Handling

- API errors return RFC 7807 problem-details JSON. Web and desktop clients render them in a consistent error toast (Ops Terminal style — sharp red border, marker code `/ERR-{kind}`).
- Service-level fatal errors (DPAPI fail, DB corruption) log to `logs/service.log` and the service refuses to start; the desktop client detects this on first request and routes to a "service unavailable" recovery page with instructions.
- Backup failures are categorized (existing `BackupRunner` already does this) — `CONNECTION_TIMEOUT`, `AUTHENTICATION_ERROR`, `PROMPT_NOT_DETECTED`, `UNKNOWN`. Each maps to a user-facing message and a remediation hint shown in the live feed.

## 10. "Ops Terminal" Design Language

Single source of truth: `app_v4/web/src/styles/tokens.css`. Translated to QSS via a tiny script for the desktop shell. Both clients ship visually identical.

### 10.1 Tokens

```css
:root {
  /* Surfaces */
  --ink: #0a0a0a;          /* base */
  --ink-2: #111111;
  --surface: #141414;
  --surface-2: #1a1a1a;
  --line: #262626;
  --line-2: #333333;

  /* Foreground */
  --bone: #fafaf7;
  --bone-2: #e5e5e2;
  --muted: #737373;
  --muted-2: #525252;

  /* Accents */
  --amber: #ffb800;        /* radar amber — signature */
  --amber-2: #ffd166;
  --red: #ff3838;          /* surgical, alerts only */
  --green: #4ade80;
  --cyan: #22d3ee;
  --violet: #a78bfa;       /* auth events only */

  /* Type */
  --font-mono: 'JetBrains Mono', monospace;
  --font-body: 'Geist', system-ui, sans-serif;
  --font-display: 'Instrument Serif', serif;
}
```

### 10.2 Typography rules

- All numbers use `font-feature-settings: 'tnum' 1, 'zero' 1;` for tabular alignment.
- Headlines are sentence-case editorial English with a serif italic phrase mid-sentence as accent (`Twelve switches, *three-forty-eight* backups, one anomaly.`). Headlines are 44 px, weight 300, letter-spacing −0.04em.
- Section labels are JetBrains Mono 10 px uppercase, letter-spacing 0.18 em.
- Marker codes (`/01 · INV`, `/REF DSH-001`) appear in muted gray, top-right of every panel and KPI cell.

### 10.3 Geometry rules

- **No border-radius** above 4 px on functional elements. Buttons and inputs are sharp.
- Grid paper background (64 px squares, 1 px lines, 4 % opacity) on the body.
- Each KPI cell has 6 px corner crosshairs in amber at top-left and bottom-right (`::before` and `::after`).
- Dashed dividers (3-3 stroke) inside lists; solid 1 px lines between sections.
- A diagonal stripe (repeating-linear-gradient) under the topbar, amber at 30 % opacity.

### 10.4 Motion

- Subtle scanline animation across the viewport (8 s linear infinite, amber line at 0.6 opacity).
- Blinking caret in the brand glyph (1 s steps).
- Live feed rows enter with a 0.4 s typewriter-style stagger on first paint.
- Chart lines draw on mount via `stroke-dasharray` + transition.
- That is it. No floating cards, no bouncy hover. Restraint is the point.

### 10.5 Color usage rules

- `--amber` is the **only** accent for affirmative interactive elements (active nav, primary action button, highlight ring).
- `--red` is reserved for failures and alerts. Never use red for "danger zone" labels — use a red marker code instead.
- `--green` is for "running / online / success" status indicators only.
- `--violet` is for auth events in the live feed.
- All other UI is bone, muted, and ink. Bone for data, muted for chrome, ink for surfaces.

## 11. Migration Plan

### 11.1 What v3 users keep

- All existing backup files (`backups/`) — same folder layout. v4 reads them as-is.
- Existing SQLite database — v4 runs Alembic migrations to add `users`, `sessions`, `audit_log` and a few columns.
- Existing master passphrase — wizard reads `.service_passphrase` (or prompts), stores via DPAPI, deletes the legacy file.

### 11.2 Cutover

1. v4 ships as separate installer (different product code).
2. Installing v4 stops the v3 service if present.
3. v4 setup wizard offers "Migrate from v3.5.x" — points to v3 install dir, copies DB and backups, runs migrations.
4. v3 stays installed; admin uninstalls when comfortable. No automatic v3 removal.

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Scope is large — dual stack + new arch + new design | Single big-bang in a new folder removes coupling risk. Existing `app/` keeps shipping as a fallback. |
| DPAPI is per-user; service account change breaks decrypt | Setup wizard records the service account; settings warn if it changes. Recovery path = re-run wizard. |
| Hybrid Qt + WebEngine adds .exe size (~120-180 MB) | Acceptable trade-off given the design fidelity goal. Alternative would be re-implementing Recharts in Qt — rejected. |
| Qt's QSS isn't 1:1 with CSS | Maintain a small generator that maps CSS tokens to QSS plus a manual review checklist for Qt-only properties. |
| WebSocket disconnects on flaky LAN | Auto-reconnect with exponential backoff in `useWebSocket()` hook; topbar pulse turns amber when disconnected, red after 30 s. |
| Audit log table grows unbounded | Retention policy: trim entries older than 90 days nightly via the existing `RetentionService`. |

## 13. Out of Scope (Explicitly Deferred)

- Multi-tenant / org-level support.
- LDAP / Active Directory SSO.
- Mobile app (web client must be responsive enough for tablet though — desktop first, tablet acceptable, phone not targeted).
- Backup of non-Allied-Telesis devices.
- Backup encryption-at-rest (current backups are plain text on disk; out of scope for v4 unless requirements change).

## 14. Open Questions for Future Iterations

- Should `Operator` be allowed to view the audit log (read-only)? Currently locked to Admin. *Default: Admin-only for v4.0; revisit if Operator team requests it.*
- Should the dashboard have a "Maintenance window" toggle that pauses scheduled backups? *Default: not in v4.0.*
- Should there be a CLI? *Default: not in v4.0; service exposes the same API so a thin CLI client can be built later.*

---

## Appendix A — Visual Reference

The Dashboard mockup that establishes the Ops Terminal language is preserved at `.superpowers/brainstorm/<session>/content/ops-terminal.html`. Treat it as the visual ground truth for both clients.

## Appendix B — Plan Splitting

This spec is large and will be decomposed into multiple implementation plans in the next phase:

1. **Plan 1** — Backend service skeleton (FastAPI + auth + DB migrations + DPAPI + tests), no UI.
2. **Plan 2** — Web client foundations (auth, layout, Dashboard) and CSS tokens.
3. **Plan 3** — Web client remaining pages.
4. **Plan 4** — Desktop client shell + setup wizard.
5. **Plan 5** — Desktop client view migration.
6. **Plan 6** — Installer + migration tool from v3.5.x.

Each plan is a separate brainstorming → planning → implementation cycle.
