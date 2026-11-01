<p align="center">
  <img src="Icon%20Aplikasi/Icon%20NCM.png" alt="NCM v4" width="120" height="120"/>
</p>

<h1 align="center">NCM v4: Network Configuration Manager</h1>

<p align="center">
  <b>English</b> · <a href="README.id.md">Bahasa Indonesia</a>
</p>

<p align="center">
  Automated switch backups, configuration drift review, and ISO/IEC 27001 A.8.9 evidence.<br/>
  Windows desktop app in a single executable (FastAPI + React).
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-4.7.0-blue" alt="Version"/>
  <img src="https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React"/>
  <img src="https://img.shields.io/badge/PySide6-Qt%206-41CD52?logo=qt&logoColor=white" alt="PySide6"/>
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white" alt="Platform"/>
</p>

## Contents

- [Why NCM v4](#why-ncm-v4)
- [Features](#features)
- [Supported devices](#supported-devices)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Getting started](#getting-started)
- [Building from source](#building-from-source)
- [Development](#development)
- [Data and folders](#data-and-folders)
- [Integration API](#integration-api)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [License](#license)

## Why NCM v4

Most network teams back up switch configurations, but few can show an auditor that the configurations are actually reviewed. NCM v4 covers both. One Windows executable runs scheduled backups over SSH, Telnet, or SNMP, compares every backup with an approved baseline, puts changes into a review queue, sends reminders, and exports ISO/IEC 27001 A.8.9 evidence. When you close the window it keeps running in the system tray.

The executable is both server and client. The desktop shell starts a uvicorn thread that serves the REST API and the bundled React interface on port 8443, so there is nothing else to install and no external database.

## Features

### Backup and drift management

- Backups over SSH (asyncssh), Telnet (telnetlib3), and WebSmart SNMP (v1/v2), with port and credentials set per device.
- Enable-mode support for CLIs that need it, such as Ruijie, with a separate enable password.
- MikroTik RouterOS dual backup: a text export (`/export compact`) for diffing and a binary `/system backup` downloaded over SFTP.
- Golden baselines per switch or per model. A baseline always points to a successful backup as its source; a baseline without a source is refused, so drift detection cannot be silently inactive. Existing baselines can be repointed to a newer backup.
- Every backup is compared with its baseline. Drift opens a pending review with a structured summary (VLANs added, removed, or renamed, port changes, hostname) and a unified diff.
- The diff viewer has a decode view, and reviews can generate CLI rollback commands from the difference between baseline and current configuration.
- A Review button on each baseline compares the golden and latest configurations at any time, even when the switch is offline.
- Full history of backups, diffs, review decisions, and audit events, all searchable and exportable.

### ISO/IEC 27001 A.8.9 compliance

- Review cycle with a configurable re-attestation interval in months (default 6) and calendar-accurate due dates.
- Dedicated baseline review workflow, including attestation of clean matches and a save-cycle action.
- Reviewer identity and review date are recorded on each decision, and review records can be deleted by authorized users.
- Compliance panel: baseline coverage, pending and flagged reviews, switches without a baseline, and reminders due.
- Per-switch compliance report as CSV, Excel, or PDF, including the next review date.
- Daily reminder digest by email for pending reviews, missing baselines, and due re-attestations. Reminders stop once baselines are re-attested.

### Notifications

- Event emails with descriptive subjects, for example:
  - `[NCM] BACKUP GAGAL — SW-CORE-01 (backup #123)`
  - `[NCM] BACKUP OK — SW-CORE-01 (backup #124) — config BERUBAH`
  - `[NCM] REVIEW PENDING #45 — SW-CORE-01 (drift terdeteksi)`
  - `[NCM] REVIEW APPROVED #45 — SW-CORE-01 — oleh admin`
- Separate switches for backup failure alerts (on by default), backup success alerts (opt-in), and review events.
- Editable HTML reminder template with `{{variables}}`, sent as multipart HTML and text, with a preview button.
- Telegram and webhook channels. Webhook payloads are signed with HMAC-SHA256.

### Security

- JWT authentication with short-lived access tokens and refresh tokens, and roles for admin, operator, and viewer.
- Scoped API keys (stored as SHA-256 hashes, with only the prefix shown) for integrations. Scopes and presets can be edited after creation; keys can be revoked or deleted permanently.
- Device credentials encrypted at rest. The master key is protected with Windows DPAPI.
- Account lockout and password policy.
- Audit log of every sensitive action: baselines, reviews, API keys, settings, and retention.

### Desktop experience

- Closing the window keeps the backend and scheduler running in the tray. The tray menu item Keluar is the only real exit.
- Setup wizard on first launch: master passphrase, admin account, and the service bind address. The default `0.0.0.0` exposes the service to the local network, and the wizard warns about it.
- Dark operations-console interface with a live device grid, backup charts, and a diff viewer.

### Integrations

- DataGuard: automatic and on-demand sync of device names and models.
- Read endpoints for structured network documentation, used by DataGuard and other tools.

## Supported devices

| Access method | Devices |
|---|---|
| SSH or Telnet | Allied Telesis AlliedWare Plus and Dell Networking, with structured config parsing; Ruijie and other CLI switches, compared as plain text diffs |
| WebSmart SNMP v1/v2 | Allied Telesis WebSmart models, with structured parsing |
| MikroTik RouterOS | Text export plus binary backup over SFTP |

Model names are detected from the configuration text for Allied Telesis, Dell, Aruba, Cisco Catalyst, Juniper, MikroTik, and Ruijie devices.

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.13, FastAPI, uvicorn, Pydantic v2 |
| Database | SQLite through SQLAlchemy 2 async (aiosqlite) |
| Desktop shell | PySide6 (Qt 6): native window, tray, and a WebView for the SPA |
| Frontend | React 19, TypeScript, Vite, TanStack Query, wouter, recharts |
| Network access | asyncssh, telnetlib3, SNMP |
| Scheduling | APScheduler for backups, retention, and reminder digests |
| Security | JWT, argon2, API keys, Windows DPAPI |
| Reports | reportlab (PDF), openpyxl (XLSX), csv |
| Notifications | SMTP (multipart HTML and text), Telegram, webhooks |
| Packaging | PyInstaller, Inno Setup |
| Tests | pytest, pytest-asyncio, pytest-qt; Vitest and Testing Library |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                 ncm-v4-desktop.exe (PyInstaller)             │
├──────────────────────────────────────────────────────────────┤
│  PySide6 shell            │  uvicorn thread (port 8443)      │
│  window · tray · login    │  FastAPI REST API + WebSocket    │
│        │                  │        │                         │
│        └──► SpaView (WebView) ──► React SPA (bundled static) │
├──────────────────────────────────────────────────────────────┤
│  ServiceRuntime                                              │
│  BackupService · ReviewService · SchedulerService            │
│  RetentionService · Notifier (SMTP / Telegram / webhook)     │
├──────────────────────────────────────────────────────────────┤
│  Data: SQLite (app.db) + backup files on disk                │
│  Network: asyncssh · telnetlib3 · SNMP · MikroTik client     │
└──────────────────────────────────────────────────────────────┘
```

## Getting started

Requirements: Windows 10 or 11 and network access to your switches over SSH, Telnet, or SNMP.

1. Build or obtain `dist\ncm-v4-desktop\ncm-v4-desktop.exe`.
2. Run it. The first launch opens the setup wizard: master passphrase, admin account, and bind address.
3. Add switches and credentials, run a backup, then create a baseline from it.

## Building from source

Requirements: Python 3.13 and Node.js 20 or newer.

```powershell
# 1) Python environment (use the full requirements; a stripped venv breaks the exe)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r app_v4\requirements-v4.txt

# 2) Install frontend dependencies
npm --prefix app_v4/web install

# 3) Build the web bundle and the desktop exe
.\installer\v4\build_app.ps1
# → dist\ncm-v4-desktop\ncm-v4-desktop.exe
```

`build_app.ps1` copies `dist\ncm-v4-desktop\data` (database and master keys) aside before PyInstaller runs and restores it afterwards. If you run PyInstaller by hand with `--clean`, back up that folder first or the encrypted credentials become unreadable.

Other files in `installer\v4\`: `NCMv4.iss` (Inno Setup installer), `install_service.ps1` and `uninstall_service.ps1` (run the backend as the `NCMv4Backend` Windows service), and `generate_cert.ps1` (TLS certificate).

## Development

```powershell
# Backend with interactive API docs at http://127.0.0.1:8443/docs
python -m uvicorn app_v4.service.main:app --port 8443

# Frontend dev server
npm --prefix app_v4/web run dev
```

Tests:

```powershell
.venv\Scripts\python.exe -m pytest app_v4\tests -q   # backend
npm --prefix app_v4/web run test                     # frontend
```

### Project layout

```
app_v4/
  core/            settings, paths, auth service, runtime settings
  data/            SQLAlchemy models and repository
  net/             SSH, Telnet, WebSmart, MikroTik clients and config parsers
  service/         FastAPI app, backup, review, scheduler, retention, notifications
    api/           REST routers (switches, backups, reviews, api_keys, network_doc, ...)
  desktop/         PySide6 shell: main window, tray, setup wizard
  web/             React SPA (Vite)
  tests/           pytest suite
installer/v4/      build script, PyInstaller spec, Inno Setup script, service scripts
Dokumentasi/       user guide, API documentation, manual
```

## Data and folders

| Path next to the exe | Contents |
|---|---|
| `data\app.db` | SQLite database: switches, backups, reviews, audit |
| `data\master.key` / `master.dpapi` | DPAPI-protected master key. Never commit or share it |
| `backups\<switch>\<date>\` | Configuration snapshots and `.diff` files |
| `data\runtime_settings.json` | Notification, review cycle, and retention settings |
| `logs\` | Rotating application logs |

## Integration API

Integrations authenticate with either a JWT or a scoped API key. The interactive reference is available in the app under Settings, and in [Dokumentasi/Dokumentasi API.md](Dokumentasi/Dokumentasi%20API.md). `scripts/gen_api_reference.py` regenerates the in-app reference.

## Troubleshooting

| Problem | What to check |
|---|---|
| The exe shows an old icon | Windows icon cache. Restart Explorer or pin the shortcut again |
| The backend does not start | Make sure `data\` is writable. Antivirus software may block the bundled exe |
| Backup failed with AUTH or timeout | Credentials, enable password, and reachability under Switches |
| Reminder emails never arrive | Every gate: Enable notifications, Enable email reminders, SMTP host and recipients |
| Other machines cannot reach the service | The bind address chosen in the setup wizard and the Windows firewall |
| Forgotten master passphrase | Recovery is impossible by design. Restore from a backup or start fresh |

## Documentation

- [User guide](Dokumentasi/user_guide.md)
- [API documentation](Dokumentasi/Dokumentasi%20API.md)
- [Walkthrough](walkthrough.md) and [implementation plan](implementation_plan.md)

## License

Proprietary, for internal use. No license is granted for redistribution.

Developed by Yohanes Octavian Rizky ([@torpedoliar](https://github.com/torpedoliar)).
