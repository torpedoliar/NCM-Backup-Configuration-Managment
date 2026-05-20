# NCM v4 Phase 8 Installer and Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package v4 as a Windows installer with service install/uninstall flow, HTTPS certificate setup, and v3.5.x migration tooling.

**Architecture:** Keep installer assets under `installer/v4/`, keep migration logic testable under `app_v4/tools/`, and keep Windows service commands in PowerShell scripts called by the installer. Tests cover migration behavior without touching real services.

**Tech Stack:** Python, Inno Setup script, PowerShell, pytest, SQLite.

---

## File Structure

- Create: `installer/v4/NCMv4.iss` — Inno Setup installer script.
- Create: `installer/v4/install_service.ps1` — installs Windows service.
- Create: `installer/v4/uninstall_service.ps1` — stops/removes Windows service.
- Create: `installer/v4/generate_cert.ps1` — self-signed cert generation.
- Create: `app_v4/tools/__init__.py`
- Create: `app_v4/tools/migrate_v3.py`
- Create: `app_v4/tools/cert_fingerprint.py`
- Modify: `app_v4/cli.py` — add `migrate-v3` command entry.
- Modify: `app_v4/core/key_envelope.py` — expose legacy passphrase migration helper if not already available.
- Test: `app_v4/tests/test_migrate_v3.py`
- Test: `app_v4/tests/test_cert_fingerprint.py`

### Task 1: v3 Migration Tool

**Files:**
- Create: `app_v4/tools/__init__.py`
- Create: `app_v4/tools/migrate_v3.py`
- Test: `app_v4/tests/test_migrate_v3.py`

- [ ] **Step 1: Write failing migration test**

Create `app_v4/tests/test_migrate_v3.py`:

```python
from pathlib import Path

from app_v4.tools.migrate_v3 import MigrationResult, migrate_v3_install


class FakeEnvelopeStore:
    def __init__(self):
        self.saved = None
    def save(self, master_passphrase: str, jwt_secret: bytes):
        self.saved = (master_passphrase, jwt_secret)


def test_migrate_v3_copies_database_backups_and_passphrase(tmp_path):
    source = tmp_path / "v3"
    target = tmp_path / "v4"
    source.mkdir()
    (source / "ncm.db").write_bytes(b"sqlite")
    (source / "backups").mkdir()
    (source / "backups" / "sw01.txt").write_text("config", encoding="utf-8")
    (source / ".service_passphrase").write_text("legacy-secret", encoding="utf-8")
    store = FakeEnvelopeStore()

    result = migrate_v3_install(source, target, envelope_store=store, jwt_secret=b"1" * 32)

    assert result == MigrationResult(database_copied=True, backups_copied=1, legacy_passphrase_migrated=True)
    assert (target / "data" / "ncm.db").read_bytes() == b"sqlite"
    assert (target / "backups" / "sw01.txt").read_text(encoding="utf-8") == "config"
    assert store.saved == ("legacy-secret", b"1" * 32)
    assert not (source / ".service_passphrase").exists()
```

- [ ] **Step 2: Run failing test**

```powershell
rtk python -m pytest app_v4/tests/test_migrate_v3.py -v
```

Expected: fail because migration tool missing.

- [ ] **Step 3: Create migration tool**

Create `app_v4/tools/__init__.py`:

```python
"""NCM v4 operational tools."""
```

Create `app_v4/tools/migrate_v3.py`:

```python
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MigrationResult:
    database_copied: bool
    backups_copied: int
    legacy_passphrase_migrated: bool


def migrate_v3_install(source_dir: Path, target_dir: Path, envelope_store, jwt_secret: bytes) -> MigrationResult:
    source_dir = Path(source_dir)
    target_dir = Path(target_dir)
    data_dir = target_dir / "data"
    backup_target = target_dir / "backups"
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_target.mkdir(parents=True, exist_ok=True)

    database_copied = False
    for candidate in [source_dir / "ncm.db", source_dir / "data" / "ncm.db"]:
        if candidate.exists():
            shutil.copy2(candidate, data_dir / "ncm.db")
            database_copied = True
            break

    backups_copied = 0
    source_backups = source_dir / "backups"
    if source_backups.exists():
        for path in source_backups.rglob("*"):
            if path.is_file():
                relative = path.relative_to(source_backups)
                destination = backup_target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                backups_copied += 1

    legacy_passphrase_migrated = False
    for legacy in [source_dir / ".service_passphrase", source_dir / ".gui_passphrase"]:
        if legacy.exists():
            passphrase = legacy.read_text(encoding="utf-8").strip()
            envelope_store.save(passphrase, jwt_secret)
            legacy.unlink()
            legacy_passphrase_migrated = True
            break

    return MigrationResult(database_copied, backups_copied, legacy_passphrase_migrated)
```

- [ ] **Step 4: Run migration test**

```powershell
rtk python -m pytest app_v4/tests/test_migrate_v3.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
rtk git add app_v4/tools app_v4/tests/test_migrate_v3.py
rtk git commit -m "feat: add v4 migration tool"
```

### Task 2: Certificate Fingerprint Helper

**Files:**
- Create: `app_v4/tools/cert_fingerprint.py`
- Test: `app_v4/tests/test_cert_fingerprint.py`

- [ ] **Step 1: Write failing cert test**

Create `app_v4/tests/test_cert_fingerprint.py`:

```python
from app_v4.tools.cert_fingerprint import cert_fingerprint_sha256


def test_cert_fingerprint_formats_sha256(tmp_path):
    cert = tmp_path / "cert.der"
    cert.write_bytes(b"certificate")

    fingerprint = cert_fingerprint_sha256(cert)

    assert len(fingerprint.split(":")) == 32
    assert fingerprint == fingerprint.upper()
```

- [ ] **Step 2: Create helper**

Create `app_v4/tools/cert_fingerprint.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path


def cert_fingerprint_sha256(cert_path: Path) -> str:
    digest = hashlib.sha256(Path(cert_path).read_bytes()).hexdigest().upper()
    return ":".join(digest[i:i + 2] for i in range(0, len(digest), 2))
```

- [ ] **Step 3: Run cert test**

```powershell
rtk python -m pytest app_v4/tests/test_cert_fingerprint.py -v
```

Expected: pass.

### Task 3: Service Install PowerShell Scripts

**Files:**
- Create: `installer/v4/install_service.ps1`
- Create: `installer/v4/uninstall_service.ps1`
- Create: `installer/v4/generate_cert.ps1`

- [ ] **Step 1: Create install script**

Create `installer/v4/install_service.ps1`:

```powershell
param(
  [Parameter(Mandatory=$true)][string]$InstallDir,
  [string]$PythonExe = "python"
)
$ServiceName = "NCMv4Backend"
$Args = "-m app_v4.service.windows_service"
New-Service -Name $ServiceName -BinaryPathName "`"$PythonExe`" $Args" -DisplayName "NCM v4 Backend" -StartupType Automatic
Start-Service -Name $ServiceName
```

- [ ] **Step 2: Create uninstall script**

Create `installer/v4/uninstall_service.ps1`:

```powershell
$ServiceName = "NCMv4Backend"
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
  Stop-Service -Name $ServiceName -Force
  sc.exe delete $ServiceName | Out-Null
}
```

- [ ] **Step 3: Create cert script**

Create `installer/v4/generate_cert.ps1`:

```powershell
param(
  [Parameter(Mandatory=$true)][string]$CertPath,
  [Parameter(Mandatory=$true)][string]$Password
)
$cert = New-SelfSignedCertificate -DnsName @("localhost", $env:COMPUTERNAME) -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddYears(5)
$secure = ConvertTo-SecureString -String $Password -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $CertPath -Password $secure | Out-Null
```

- [ ] **Step 4: Validate scripts parse**

```powershell
rtk powershell -NoProfile -Command "$null = [scriptblock]::Create((Get-Content installer/v4/install_service.ps1 -Raw)); $null = [scriptblock]::Create((Get-Content installer/v4/uninstall_service.ps1 -Raw)); $null = [scriptblock]::Create((Get-Content installer/v4/generate_cert.ps1 -Raw))"
```

Expected: command exits 0.

### Task 4: Inno Setup Installer Script

**Files:**
- Create: `installer/v4/NCMv4.iss`

- [ ] **Step 1: Create installer script**

Create `installer/v4/NCMv4.iss`:

```ini
#define MyAppName "NCM v4"
#define MyAppVersion "4.0.0"
#define MyAppPublisher "NCM"
#define MyAppExeName "ncm-v4-desktop.exe"

[Setup]
AppId={{A6A1DB5B-2C6D-4D2E-A59D-68C3BCA34740}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NCM v4
DefaultGroupName=NCM v4
OutputDir=..\..\dist
OutputBaseFilename=NCM-v4-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Files]
Source: "..\..\app_v4\*"; DestDir: "{app}\app_v4"; Flags: recursesubdirs ignoreversion
Source: "install_service.ps1"; DestDir: "{app}\installer"
Source: "uninstall_service.ps1"; DestDir: "{app}\installer"
Source: "generate_cert.ps1"; DestDir: "{app}\installer"

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File \"{app}\installer\install_service.ps1\" -InstallDir \"{app}\""; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File \"{app}\installer\uninstall_service.ps1\""; Flags: runhidden waituntilterminated
```

- [ ] **Step 2: Commit installer script and PowerShell scripts**

```powershell
rtk git add installer/v4/NCMv4.iss installer/v4/install_service.ps1 installer/v4/uninstall_service.ps1 installer/v4/generate_cert.ps1 app_v4/tools/cert_fingerprint.py app_v4/tests/test_cert_fingerprint.py
rtk git commit -m "feat: add v4 installer assets"
```

### Task 5: CLI Migration Entry and Final Verification

**Files:**
- Modify: `app_v4/cli.py`
- Test: `app_v4/tests/test_migrate_v3.py`

- [ ] **Step 1: Add CLI entry**

In `app_v4/cli.py`, add subcommand `migrate-v3` using existing CLI parser style:

```python
migrate_parser = subparsers.add_parser("migrate-v3")
migrate_parser.add_argument("source_dir")
migrate_parser.add_argument("target_dir")
```

When selected:

```python
from secrets import token_bytes
from app_v4.core.key_envelope import KeyEnvelopeStore
from app_v4.core.dpapi import WindowsDpapiProvider
from app_v4.tools.migrate_v3 import migrate_v3_install

store = KeyEnvelopeStore(resolve_paths(settings).master_envelope_file, WindowsDpapiProvider())
result = migrate_v3_install(Path(args.source_dir), Path(args.target_dir), store, token_bytes(32))
print(result)
```

- [ ] **Step 2: Run full verification**

```powershell
rtk python -m pytest app_v4/tests -v
```

Expected: pass.

If Inno Setup compiler is installed, run:

```powershell
rtk iscc installer/v4/NCMv4.iss
```

Expected: installer build succeeds. If `iscc` is unavailable, record that only script parse and Python tests were verified.

- [ ] **Step 3: Commit CLI entry**

```powershell
rtk git add app_v4/cli.py app_v4/tests/test_migrate_v3.py
rtk git commit -m "feat: expose v4 migration CLI"
```
