# Allied Telesis Backup Configuration Manager - Application Overview

## 1. High-Level Architecture
The application is a Windows desktop tool designed to backup and manage configurations for Allied Telesis switches. It follows a layered architecture:

- **UI Layer (`app/ui/`)**: Built with `tkinter` and `ttkbootstrap` for a modern look. Handles user interaction.
- **Service Layer (`app/services/`)**: Contains the core business logic (Backup, Schedule, Crypto, Retention, Diff).
- **Data Layer (`app/data/`)**: Manages data persistence using SQLite and SQLAlchemy.
- **Network Layer (`app/net/`)**: Handles low-level SSH (`paramiko`) and Telnet (`telnetlib3`) connections.
- **Infrastructure**: Supports running as a background Windows Service or via Task Scheduler.

## 2. Key Components

### Entry Point (`app/main.py`)
- Handles application startup.
- Manages the **Master Passphrase** (prompting or auto-login).
- Initializes core services (`CryptoService`, `ScheduleService`, `RetentionService`).
- Determines execution mode:
    - **GUI Mode**: Launches the main window (`AppWindow`).
    - **Service Mode**: Runs as a background process (via `--service` flag).

### Backup Service (`app/services/backup_service.py`)
- **`execute_backup(switch_id)`**: The core function.
    1.  Retrieves switch details and decrypts credentials.
    2.  Connects to the switch using `BackupRunner`.
    3.  Fetches the running configuration.
    4.  Calculates a SHA-256 hash to detect changes.
    5.  Saves the config to a file (organized by Switch/Date).
    6.  If changed, generates a unified diff against the previous backup.
    7.  Logs the result (success/failure) to the database.
- **Error Handling**: Categorizes errors (e.g., `CONNECTION_TIMEOUT`, `AUTHENTICATION_ERROR`) into user-friendly messages.

### Security
- **Encryption**: Credentials are encrypted using Fernet (AES-128).
- **Master Passphrase**: Required to decrypt credentials. It is **never stored** in plain text.
    - *Auto-login* saves an obfuscated version (XOR) for convenience, but warns about security risks.

### Scheduling & Background Execution
- **`ScheduleService`**: Uses `apscheduler` to run backups at defined intervals (15m, 1h, Daily, etc.).
- **Windows Service**: Can be installed to run 24/7 without the GUI.
- **Task Scheduler**: Fallback mechanism if Windows Service integration fails.

## 3. Project Structure

```
app/
├── main.py                 # Entry point
├── ui/                     # User Interface
│   ├── app_window.py       # Main container
│   ├── dashboard_view.py   # Overview
│   ├── inventory_view.py   # Switch management
│   └── ...
├── services/               # Business Logic
│   ├── backup_service.py   # Backup execution
│   ├── crypto_service.py   # Encryption/Decryption
│   └── ...
├── net/                    # Network Communication
│   ├── runner.py           # Abstraction for backup execution
│   ├── ssh_client.py       # SSH implementation
│   └── telnet_client.py    # Telnet implementation
└── data/                   # Database
    ├── db.py               # DB connection
    ├── models.py           # SQLAlchemy models
    └── repository.py       # Data access methods
```

## 4. Data Flow (Backup Process)
1.  **Trigger**: User clicks "Backup" (GUI) or Scheduler triggers job.
2.  **Service**: `BackupService` receives the request.
3.  **Data**: Fetches Switch info and Credentials from DB.
4.  **Crypto**: Decrypts the password using the Master Key in memory.
5.  **Network**: `BackupRunner` connects to the switch (SSH/Telnet).
6.  **Switch**: Executes `show running-config`.
7.  **Processing**: Output is captured, normalized, and hashed.
8.  **Storage**: File saved to `backups/` folder.
9.  **Database**: `Backup` record created with status and file path.
10. **UI**: Dashboard/History view updates with the new status.
