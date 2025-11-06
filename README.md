# ATI Switch Configuration Backup Manager

A production-ready Windows desktop application for backing up and tracking configuration history for Allied Telesis switches.

## Features

- **Multi-Protocol Support**: Connect via SSH or Telnet with custom ports
- **Secure Credential Vault**: Encrypted storage with master passphrase (Fernet AES-128)
- **Automated Backups**: Schedule periodic configuration pulls (15m/1h/6h/12h/24h)
- **Diff Viewer**: Line-numbered unified diff with syntax highlighting
- **30-Day Retention**: Automatic cleanup of old backups with minimum retention
- **Non-Blocking UI**: Background threads for network operations
- **Comprehensive Logging**: Rotating log files with 7-day retention
- **Retry Logic**: Exponential backoff for connection failures
- **Prompt Detection**: Automatic CLI prompt and paging detection

## Quick Start

```powershell
# 1. Install dependencies (Python 3.11+ required)
pip install -r requirements.txt

# 2. Run application
python -m app.main

# 3. Build standalone executable
.\build.ps1
```

The application will prompt for a master passphrase on first launch to encrypt credentials.

## Project Structure

```
app/
├── main.py                 # Entry point
├── ui/                     # User interface modules
│   ├── app_window.py
│   ├── inventory_view.py
│   ├── credentials_view.py
│   ├── history_view.py
│   ├── diff_view.py
│   ├── schedules_view.py
│   └── settings_view.py
├── net/                    # Network clients
│   ├── ssh_client.py
│   ├── telnet_client.py
│   └── runner.py
├── data/                   # Database layer
│   ├── db.py
│   ├── models.py
│   └── repository.py
├── services/               # Business logic
│   ├── backup_service.py
│   ├── diff_service.py
│   ├── schedule_service.py
│   ├── retention_service.py
│   ├── crypto_service.py
│   └── export_service.py
└── config/                 # Configuration
    ├── appsettings.yaml
    └── logging_config.py
```

## Usage

### First Launch
1. Set a master passphrase (min 8 characters)
2. Keep it safe - it's NOT stored!

### Adding Switches
1. Navigate to **Inventory** tab
2. Click **Add Switch**
3. Fill in details and save

### Managing Credentials
1. Go to **Credentials** tab
2. Add credentials (username, password, enable password)
3. All data is encrypted at rest

### Manual Backup
1. Select switch in **Inventory**
2. Click **Get Data**
3. View status in real-time

### Scheduling
1. Go to **Schedules** tab
2. Add schedule for switch
3. Choose interval (15m/1h/6h/12h/24h)

### Viewing Diffs
1. Navigate to **Backup History**
2. Select switch and two backups
3. Click **Show Diff**

## Security

- AES-128 encryption (Fernet) for credentials
- Master passphrase derived using PBKDF2
- Passphrase never stored on disk
- 100,000 iterations for key derivation

## Building

```powershell
.\build.ps1
```

Output: `dist\ATISwitchBackup.exe`

## Troubleshooting

**Connection fails**: Check IP, port, firewall, credentials

**Prompt not detected**: Customize in Settings > Prompt Patterns

**Master passphrase lost**: Delete `data/master.key` and `data/app.db` (loses all data)

## Requirements

- Python 3.11+
- Windows 10/11
- Network access to switches

## Testing

Run the test suite:

```powershell
# Run all tests
python -m pytest app/tests/ -v

# Or using unittest
python -m unittest discover app/tests/
```

## Architecture

### Database Schema
- **Credential**: Encrypted credentials (username, password, enable_password)
- **Switch**: Switch configurations (name, IP, protocol, port, credential_id)
- **Backup**: Backup records (switch_id, file_path, hash, timestamp, success)
- **Job**: Scheduled jobs (switch_id, interval, enabled, last_ran_at)

### Network Flow
1. Connect (SSH/Telnet)
2. Send `enable` command (with optional password)
3. Send `terminal length 0` to disable paging
4. Send `show running-config`
5. Capture full output (handle paging if needed)
6. Normalize line endings
7. Save to `backups/<switch>/<date>/<time>_running-config.txt`

### Security
- **Encryption**: Fernet (symmetric AES-128 in CBC mode)
- **Key Derivation**: PBKDF2-HMAC-SHA256 with 100,000 iterations
- **Salt Storage**: Random 16-byte salt stored in `data/master.key`
- **Credential Storage**: Encrypted JSON blobs in SQLite database
- **Master Passphrase**: Never stored on disk, only in memory during session

## License

Proprietary - Internal Use Only
