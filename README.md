<p align="center">
  <img src="Icon%20Aplikasi/Icon%20NCM.png" alt="NCM v4" width="120" height="120"/>
</p>

<h1 align="center">NCM v4 — Network Configuration Manager</h1>

<p align="center">
  <strong>Automated switch backup, config-drift review & ISO 27001 A.8.9 compliance</strong><br/>
  Desktop app · Single exe · FastAPI + React · Windows
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13-blue" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React-19-61dafb" alt="React"/>
  <img src="https://img.shields.io/badge/PySide6-QT6-41cd52" alt="PySide6"/>
  <img src="https://img.shields.io/badge/tests-418%20%2B%2094-brightgreen" alt="Tests"/>
  <img src="https://img.shields.io/badge/platform-Windows-lightgrey" alt="Platform"/>
</p>

---

## Why NCM v4

Network teams back up switch configs but rarely *prove* they manage them. NCM v4 closes that gap:
one Windows exe runs a full backup + review pipeline — scheduled backups over SSH/Telnet/SNMP,
automatic drift detection against golden baselines, a human review queue, scheduled email
reminders, and exportable ISO 27001 A.8.9 evidence. Close the window and it keeps working in the
system tray.

**One exe = server + app.** The desktop shell boots a uvicorn thread serving the REST API and the
bundled React UI on `http://localhost:8443` — no separate installation, no external database.

## Feature Highlights

### Backup & Drift Management
- **Multi-protocol backup** — SSH (asyncssh), Telnet (telnetlib3), WebSmart SNMP (V1/V2); per-device port & credentials
- **Golden baselines** — per-switch or per-model templates; the backend snapshots the latest successful backup as the golden source (a baseline without a source is refused, so drift detection can never be silently inactive)
- **Automatic drift detection** — every backup is compared to its baseline; drift opens a **pending review** with a structured summary (VLANs added/removed/renamed, port changes, hostname) plus a unified diff
- **On-demand review** — a *Review* button on each baseline re-compares golden vs latest config anytime, without waiting for the monthly cycle; the switch doesn't even need to be online
- **Full history** — every backup, diff, review decision, and audit event is queryable and exportable

### ISO 27001 A.8.9 Compliance
- **Review cycle** — configurable N-month re-attestation interval (default 6) with calendar-precise due dates
- **Compliance panel** — baseline coverage %, pending/flagged reviews, switches missing baselines, reminders due
- **Evidence export** — per-switch compliance report as CSV / Excel / PDF, including a *Next review* column
- **Reminder emails** — daily digest of pending reviews, missing baselines, and reminders due; stops once baselines are re-attested

### Notifications
- **Event emails with informative subjects**:
  - `[NCM] BACKUP GAGAL — SW-CORE-01 (backup #123)`
  - `[NCM] BACKUP OK — SW-CORE-01 (backup #124) — config BERUBAH`
  - `[NCM] REVIEW PENDING #45 — SW-CORE-01 (drift terdeteksi)`
  - `[NCM] REVIEW APPROVED #45 — SW-CORE-01 — oleh admin`
- **Toggles** — backup-failure alerts (default on), backup-success alerts (opt-in), review events (pending + decisions)
- **Custom HTML template** — edit the reminder email body in Settings with `{{variables}}` (live data, XSS-escaped, multipart HTML+text, preview send button)
- **Telegram & webhook** channels for drift alerts

### Security
- **JWT auth** (short-lived access + refresh tokens), role-based access (admin / operator / viewer)
- **API keys** (SHA-256 hashed, prefix-shown, revoke or permanently delete) for read-only structured network-doc endpoints
- **Credentials encrypted at rest** — master key protected by Windows **DPAPI**; account lockout, password policy
- **Full audit log** of every sensitive action (baselines, reviews, API keys, settings, retention)

### Desktop Experience
- **Close-to-tray** — closing the window keeps the backend + scheduler running; tray menu *Keluar* is the only true exit
- **Native app icon** on exe, window, and tray
- **Ops-terminal UI** — dark theme, live fleet grid, backup charts, diff viewer

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.13, **FastAPI**, uvicorn, Pydantic v2 |
| Database | **SQLite** via SQLAlchemy 2 async (aiosqlite) |
| Desktop shell | **PySide6 (Qt 6)** — native window + tray, WebView hosting the SPA |
| Frontend | **React 19 + TypeScript**, Vite, TanStack Query, wouter, recharts |
| Network access | asyncssh (SSH), telnetlib3 (Telnet), SNMP for WebSmart |
| Scheduling | **APScheduler** — backups, retention, reminder digests |
| Security | JWT, argon2, API keys, Windows DPAPI master-key protection |
| Reporting | reportlab (PDF), openpyxl (XLSX), stdlib csv |
| Notifications | SMTP multipart (HTML+text), Telegram, webhooks |
| Packaging | **PyInstaller** → single `ncm-v4-desktop.exe` bundle |
| Testing | pytest + pytest-asyncio + pytest-qt (418), Vitest + Testing Library (94) |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                 ncm-v4-desktop.exe (PyInstaller)             │
├──────────────────────────────────────────────────────────────┤
│  PySide6 shell            │  uvicorn thread (localhost:8443) │
│  window · tray · login    │  FastAPI REST API + WebSocket    │
│        │                  │        │                          │
│        └──► SpaView (WebView) ──► React SPA (bundled static) │
├──────────────────────────────────────────────────────────────┤
│  ServiceRuntime                                              │
│  BackupService · ReviewService · SchedulerService            │
│  RetentionService · Notifier (SMTP/Telegram/webhook)         │
├──────────────────────────────────────────────────────────────┤
│  Data layer: SQLite (app.db) + backup files on disk          │
│  Network layer: asyncssh · telnetlib3 · SNMP                 │
└──────────────────────────────────────────────────────────────┘
```

### Project Structure

```
📦 NCM-Backup-Configuration-Managment/
├── app_v4/
│   ├── core/                 # Settings, paths, auth service, runtime settings
│   ├── data/                 # SQLAlchemy models + repository
│   ├── net/                  # SSH / Telnet / WebSmart clients, config parsers
│   ├── service/              # FastAPI app, backup/review/scheduler services
│   │   └── api/              # REST routers (switches, backups, reviews, ...)
│   ├── desktop/              # PySide6 shell: main window, tray, setup wizard
│   └── web/                  # React SPA source (Vite)
│       └── src/pages/        # Dashboard, Baselines, Config Review, Settings...
├── installer/v4/             # PyInstaller spec (icon, hidden imports)
├── app_v4/tests/             # pytest suite (418 tests)
├── app_v4/web/src/**.test    # Vitest suite (94 tests)
└── Dokumentasi/              # User guide, API docs
```

## Quick Start

### Prerequisites
- **Windows 10/11**
- Network reachability to your switches (SSH/Telnet/SNMP)
- For development: Python 3.13, Node.js 20+

### Run the exe (end users)

1. Build or obtain `dist\ncm-v4-desktop\ncm-v4-desktop.exe`
2. Run it — first launch opens the setup wizard (master passphrase + admin account)
3. Add switches & credentials, run a backup, then create a baseline from it

### Build from source

```powershell
# 1) Frontend bundle
npm --prefix app_v4/web install
npm --prefix app_v4/web run build

# 2) Python environment (full requirements — a stripped venv breaks the exe)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-v4.txt

# 3) Desktop exe
pyinstaller installer\v4\ncm-v4-desktop.spec --clean --noconfirm
# → dist\ncm-v4-desktop\ncm-v4-desktop.exe
```

> ⚠️ **PyInstaller `--clean` wipes `dist\ncm-v4-desktop\data`** (app.db + master keys).
> Back up that folder first, or credential blobs get orphaned.

### Development mode

```powershell
# Backend + API docs (http://127.0.0.1:8443/docs)
python -m uvicorn app_v4.service.main:app --port 8443

# Frontend dev server
npm --prefix app_v4/web run dev
```

### Testing

```powershell
# Backend (418 tests)
.venv\Scripts\python.exe -m pytest app_v4\tests -q

# Frontend (94 tests)
npm --prefix app_v4/web run test
```

## Data & Folders

| Path (next to exe) | Contents |
|---|---|
| `data\app.db` | SQLite — switches, backups, reviews, audit |
| `data\master.key` / `master.dpapi` | DPAPI-protected master key (**never commit, never share**) |
| `backups\<switch>\<date>\` | Config snapshots + `.diff` files |
| `data\runtime_settings.json` | Notification, review-cycle, retention settings |
| `logs\` | Rotating application logs |

## Documentation

- 📘 [User Guide](Dokumentasi/user_guide.md)
- 📗 [API Documentation](Dokumentasi/Dokumentasi%20API.md)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Exe shows old icon | Windows icon cache — restart Explorer or re-pin the shortcut |
| Backend didn't start | Check `data\` is writable; antivirus may block bundled exe |
| Backup failed: AUTH/timeout | Verify credentials & reachability in **Switches** |
| Reminder email never arrives | Check all gates: *Enable notifications* → *Enable email reminders* → SMTP host/recipients |
| Forgot master passphrase | Recovery is impossible by design — restore from backup or start fresh |

---

<p align="center">
  <sub>NCM v4 · Proprietary — internal use</sub>
</p>
