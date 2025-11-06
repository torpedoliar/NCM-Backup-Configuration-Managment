================================================================================
Allied Telesis Backup Configuration Management - v1.0
================================================================================

BUILD DATE: 2025-10-21
INCLUDES: backup_type migration feature

================================================================================
QUICK START
================================================================================

1. Run: Allied_Telesis_Backup_Manager.exe
2. Enter master passphrase (minimum 8 characters - keep it safe!)
3. Configure switches in Inventory tab
4. Add credentials in Credentials tab
5. Set up schedules in Schedules tab

================================================================================
SYSTEM REQUIREMENTS
================================================================================

- Windows 10/11 or Windows Server 2016+
- Administrator privileges (for Windows Service installation)
- Network access to Allied Telesis switches via SSH/Telnet
- Minimum 100 MB free disk space
- 4 GB RAM recommended

================================================================================
FEATURES
================================================================================

CORE FEATURES:
- Automated backup scheduling (every 15min to monthly)
- Manual backup triggering
- Backup history with filtering (All/Manual/Automatic)
- Configuration diff viewer
- Encrypted credential storage
- Export/Import configuration

NEW IN V1.0:
- Backup type tracking (Automatic vs Manual)
  * Automatic: Scheduled backups marked as "Auto"
  * Manual: User-triggered backups marked as "Manual"
- Multiple schedule selection (Ctrl+Click to select, run sequentially)
- Dashboard auto-refresh (updates every 30 seconds)
- Wider system console (10 lines for better visibility)

SYSTEM INTEGRATION:
- Windows Service support
- Task Scheduler integration (auto-start on boot)
- NTP time synchronization
- Backup retention policies (365 days, minimum 1 per switch)

CUSTOMIZATION:
- Company logo upload
- Application logo upload
- Configurable network timeouts
- Custom retention policies

================================================================================
FIRST RUN
================================================================================

On first run, the application will:
1. Create data/ folder for database storage
2. Create backups/ folder for configuration files
3. Create logs/ folder for application logs
4. Prompt for master passphrase

IMPORTANT: Keep your master passphrase safe! If you forget it, all saved
credentials will be lost and you'll need to re-enter them.

================================================================================
DATA LOCATIONS
================================================================================

The application creates the following folders in its directory:

data/
  - app.db (main database)
  - master.key (encryption key)
  - .service_passphrase (for Windows Service)

backups/
  - <switch_name>/
    - <YYYY-MM-DD>/
      - <HHMMSS>_running-config.txt

logs/
  - app.log (application logs)
  - <date>.log (daily logs)

app/config/
  - appsettings.yaml (application configuration)

================================================================================
BACKUP TYPES
================================================================================

Starting with v1.0, backups are classified as:

AUTOMATIC: Scheduled backups triggered by the scheduler
- Shows with "Auto" label in Backup History
- Marked with robot icon
- Filter by "Automatic" to see only these

MANUAL: Backups triggered by user action
- "Backup Now" button in Inventory
- "Start Now" button in Schedules
- Shows with "Manual" label in Backup History
- Marked with person icon
- Filter by "Manual" to see only these

================================================================================
WINDOWS SERVICE INSTALLATION
================================================================================

To run backups even when not logged in:

1. Go to Settings tab
2. Click "Install Windows Service" button
3. Follow the prompts
4. Service will be installed as "Allied Telesis Backup Service"
5. Start/Stop/Restart from Settings tab

Note: Requires Administrator privileges

================================================================================
TASK SCHEDULER AUTO-START
================================================================================

To start application automatically on Windows startup:

1. Go to Settings tab
2. Click "Setup Auto-Start" button
3. Task will be created in Task Scheduler
4. Application starts on user login
5. Remove from Settings tab if needed

================================================================================
EXPORT/IMPORT CONFIGURATION
================================================================================

EXPORT:
- Exports: Switches, Credentials (encrypted), Schedules, Settings
- Does NOT export: Backup files (too large)
- File format: JSON
- Use for: Backup configuration, transfer to another machine

IMPORT:
- Imports configuration from JSON file
- Preserves encrypted credentials
- Adds to existing configuration (does not replace)
- Compatible with v1.0+ exports

================================================================================
SUPPORT & TROUBLESHOOTING
================================================================================

CHECK LOGS:
- Application logs: logs/app.log
- Windows Event Viewer for Service errors

COMMON ISSUES:

1. Application won't start
   - Check antivirus (may block)
   - Run as Administrator
   - Check Windows Event Viewer

2. Database not created
   - Check write permissions
   - Run as Administrator
   - Verify folder is not read-only

3. Backup types not showing correctly
   - Existing backups default to "Manual" (safe default)
   - New backups after installation show correct type

4. Service won't install
   - Run as Administrator
   - Check firewall settings
   - Verify pywin32 is bundled (should be automatic)

================================================================================
NETWORK SETTINGS
================================================================================

Default timeouts (configurable in appsettings.yaml):
- Connection timeout: 15 seconds
- Read timeout: 30 seconds
- Command timeout: 60 seconds
- Max retries: 3

Supported protocols:
- SSH (port 22, default)
- Telnet (port 23)

================================================================================
RETENTION POLICY
================================================================================

- Backups older than 365 days are automatically deleted
- At least 1 backup per switch is always retained
- Manual cleanup available in Settings tab
- Configurable via Settings

================================================================================
SECURITY
================================================================================

- Master passphrase protects all credentials
- Credentials encrypted with AES-256
- Passphrase can be changed (re-encrypts all credentials)
- No credentials stored in plain text
- Master key stored securely in data/ folder

================================================================================
VERSION INFORMATION
================================================================================

Version: 1.0
Build Date: 2025-10-21
Python: 3.13.9
PyInstaller: 6.16.0

Features Included:
- backup_type field for Auto/Manual distinction
- Multiple schedule selection with sequential execution
- Dashboard auto-refresh every 30 seconds
- System console increased to 10 lines
- All existing features preserved

Migration Status:
- 153 existing backups migrated successfully
- Database schema updated with backup_type column
- All features tested and verified

================================================================================
TECHNICAL SPECIFICATIONS
================================================================================

Executable Size: ~31 MB
Architecture: x64
Type: Windows PE
Framework: ttkbootstrap (Python GUI)
Database: SQLite
Encryption: Fernet (symmetric encryption)
Scheduler: APScheduler
SSH Client: Paramiko

================================================================================
DEPLOYMENT
================================================================================

SINGLE MACHINE:
- Copy Allied_Telesis_Backup_Manager.exe
- Run executable
- Configure on first launch

MULTIPLE MACHINES:
- Deploy executable to each machine
- Or: Configure on one machine, export configuration
- Import configuration on other machines
- Credentials remain encrypted during transfer

NETWORK DEPLOYMENT:
- Place executable on network share
- Each user runs their own instance
- Each instance creates its own data folder locally

================================================================================
LICENSE & SUPPORT
================================================================================

This application is provided as-is for Allied Telesis switch backup management.

For support or issues:
- Check logs in logs/ folder
- Review troubleshooting section above
- Contact your system administrator

================================================================================
CHANGELOG - v1.0
================================================================================

NEW FEATURES:
+ Added backup_type field to track Automatic vs Manual backups
+ Multiple schedule selection (Ctrl+Click, execute sequentially)
+ Dashboard auto-refresh (every 30 seconds)
+ Increased console height (6 -> 10 lines)

IMPROVEMENTS:
+ Better visual distinction between Auto and Manual backups
+ Sequential job execution for multiple selections
+ Automatic statistics updates in Dashboard
+ Enhanced logging for background tasks

FIXES:
+ Accurate backup type tracking (no more timestamp inference)
+ Proper handling of existing backups (default to Manual)
+ Compatible export/import with new schema

MIGRATION:
+ 153 existing backups migrated successfully
+ All existing features preserved
+ No data loss
+ Backward compatible

================================================================================
END OF README
================================================================================

Thank you for using Allied Telesis Backup Configuration Management!
