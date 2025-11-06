"""
Main entry point for Allied Telesis Backup Configuration Management
"""
import sys
import os
import logging
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.crypto_service import CryptoService
from app.ui.app_window import AppWindow
from app.data.db import init_db
from app.services.schedule_service import ScheduleService
from app.services.retention_service import RetentionService
from app.config.logging_config import setup_logging
from app.config.paths import get_base_dir


def get_saved_passphrase() -> str:
    """Try to load saved passphrase if auto-login enabled"""
    base_dir = get_base_dir()
    passphrase_file = base_dir / "data" / ".gui_passphrase"
    if passphrase_file.exists():
        try:
            with open(passphrase_file, 'rb') as f:
                # Simple XOR encryption for GUI auto-login
                # Not super secure but better than plaintext
                import base64
                encrypted = f.read()
                key = b'AlliedTelesisBackupGUI2025'  # Simple key
                decrypted = bytes([encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted))])
                return base64.b64decode(decrypted).decode('utf-8')
        except:
            return None
    return None

def save_passphrase(passphrase: str):
    """Save passphrase for auto-login"""
    import base64
    base_dir = get_base_dir()
    passphrase_file = base_dir / "data" / ".gui_passphrase"
    (base_dir / "data").mkdir(exist_ok=True)
    
    # Simple XOR encryption
    key = b'AlliedTelesisBackupGUI2025'
    encoded = base64.b64encode(passphrase.encode('utf-8'))
    encrypted = bytes([encoded[i] ^ key[i % len(key)] for i in range(len(encoded))])
    
    with open(passphrase_file, 'wb') as f:
        f.write(encrypted)

def prompt_master_passphrase() -> tuple:
    """Prompt user for master passphrase at startup using simpledialog"""
    from tkinter import simpledialog
    
    # Check for saved passphrase first
    saved_passphrase = get_saved_passphrase()
    if saved_passphrase:
        return saved_passphrase, True  # Auto-logged in
    
    # Create a hidden root window
    root = tk.Tk()
    root.withdraw()
    
    while True:
        passphrase = simpledialog.askstring(
            "Master Passphrase",
            "Enter master passphrase to encrypt credentials:\n"
            "(Minimum 8 characters)\n\n"
            "Keep it safe! If you forget it, all saved credentials will be lost.",
            show='*',
            parent=root
        )
        
        if passphrase is None:
            # User cancelled
            root.destroy()
            sys.exit(0)
        
        if len(passphrase) < 8:
            messagebox.showerror(
                "Invalid Passphrase",
                "Passphrase must be at least 8 characters long.",
                parent=root
            )
            continue
        
        # Ask if user wants to save for auto-login
        save_choice = messagebox.askyesno(
            "Save Passphrase?",
            "Do you want to enable AUTO-LOGIN?\n\n"
            "• You won't be prompted for passphrase next time\n"
            "• Application will start immediately\n"
            "• Passphrase stored with encryption\n\n"
            "Note: Less secure than manual entry each time.\n"
            "Only enable on trusted computers.",
            parent=root
        )
        
        if save_choice:
            save_passphrase(passphrase)
        
        # Valid passphrase
        root.destroy()
        return passphrase, False  # Manual login


def _run_service_console_mode():
    """Run the background services in console mode (for Task Scheduler)."""
    import time
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Allied Telesis Backup Service Starting (Console Mode)")
    logger.info("WARNING: Running without Windows Service integration")
    logger.info("=" * 60)
    
    try:
        # Ensure required directories exist
        base_dir = get_base_dir()
        (base_dir / "data").mkdir(exist_ok=True)
        (base_dir / "backups").mkdir(exist_ok=True)
        (base_dir / "logs").mkdir(exist_ok=True)
        
        # Get master passphrase from file
        passphrase_file = base_dir / "data" / ".service_passphrase"
        if not passphrase_file.exists():
            logger.error("Master passphrase file not found. Service cannot start.")
            logger.error("Please install service using the Settings tab in the GUI")
            sys.exit(1)
        
        with open(passphrase_file, 'r') as f:
            passphrase = f.read().strip()
        
        if not passphrase:
            logger.error("Master passphrase is empty. Service cannot start.")
            sys.exit(1)
        
        # Initialize crypto service
        crypto_service = CryptoService(passphrase)
        logger.info("Crypto service initialized")
        
        # Initialize database
        init_db()
        logger.info("Database initialized")
        
        # Start background services
        schedule_service = ScheduleService(crypto_service)
        schedule_service.start()
        logger.info("Schedule service started")
        
        retention_service = RetentionService()
        retention_service.start()
        logger.info("Retention service started")
        
        logger.info("Service is now running - monitoring scheduled backups")
        logger.info("Press Ctrl+C to stop")
        logger.info("Service will auto-restart if it crashes (configured in Task Scheduler)")
        
        # Keep service running with frequent health checks
        last_health_log = time.time()
        try:
            while True:
                time.sleep(30)  # Check every 30 seconds for faster recovery after GUI closes
                
                # Verify scheduler is running; if not, attempt restart (e.g., GUI had lock previously)
                try:
                    if not (schedule_service.scheduler and schedule_service.scheduler.running):
                        logger.info("Schedule service not running, attempting restart...")
                        schedule_service.start()
                except Exception as health_check_error:
                    logger.warning(f"Health check/restart error: {health_check_error}")
                
                # Heartbeat log every 30 minutes
                if time.time() - last_health_log >= 1800:
                    last_health_log = time.time()
                    try:
                        active_jobs = len(schedule_service.job_map)
                        logger.info(f"Service heartbeat: schedule active={schedule_service.scheduler.running if schedule_service.scheduler else False}, jobs={active_jobs}")
                    except Exception:
                        logger.info("Service heartbeat: scheduler state unknown")
                        
        except KeyboardInterrupt:
            logger.info("Service stop requested (Ctrl+C)")
        except Exception as e:
            logger.exception(f"Service loop error: {e}")
            logger.error("Service will restart automatically via Task Scheduler")
            raise  # Let it crash so Task Scheduler can restart it
        
        # Cleanup on exit
        logger.info("Shutting down services")
        schedule_service.stop()
        retention_service.stop()
        logger.info("Service stopped normally")
        
    except Exception as e:
        logger.exception("Fatal error in service")
        sys.exit(1)


def run_as_service():
    """Run application as Windows service with proper SCM integration, with fallback."""
    # Try to use pywin32 for proper service integration
    try:
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager
        
        # Use the proper Windows Service wrapper
        from app.windows_service import AlliedTelesisBackupService
        
        try:
            # Run as Windows Service (only works when launched by SCM)
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(AlliedTelesisBackupService)
            servicemanager.StartServiceCtrlDispatcher()
        except Exception as e:
            # Not launched by SCM (e.g., Task Scheduler). Fall back to console mode.
            logging.getLogger(__name__).warning(f"Service control dispatcher unavailable ({e}); falling back to console mode.")
            _run_service_console_mode()
    except ImportError:
        # pywin32 not available - fall back to simple mode
        _run_service_console_mode()


def is_windows_service_installed() -> bool:
    """Return True if AlliedTelesisBackup Windows service exists."""
    import subprocess
    try:
        result = subprocess.run(
            ['sc', 'qc', 'AlliedTelesisBackup'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def is_windows_service_running() -> bool:
    """Return True if AlliedTelesisBackup Windows service is RUNNING."""
    import subprocess
    try:
        result = subprocess.run(
            ['sc', 'query', 'AlliedTelesisBackup'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return 'running' in result.stdout.lower()
    except Exception:
        pass
    return False


def check_service_running():
    """Check if background process is running (Windows Service or Scheduled Task)."""
    import subprocess
    # Prefer Windows Service state if installed
    if is_windows_service_installed() and is_windows_service_running():
        return True
    # Fallback to Task Scheduler status (may be 'Running' or 'Ready')
    try:
        result = subprocess.run(
            ['schtasks', '/Query', '/TN', 'AlliedTelesisBackup', '/FO', 'LIST', '/V'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Consider running if status contains 'running'
            return 'running' in result.stdout.lower()
    except Exception:
        pass
    return False


def is_background_configured() -> bool:
    """Return True if EITHER Windows Service or Scheduled Task is installed (configured)."""
    if is_windows_service_installed():
        return True
    # Check Task Scheduler task presence
    import subprocess
    try:
        result = subprocess.run(
            ['schtasks', '/Query', '/TN', 'AlliedTelesisBackup'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def main():
    """Main application entry point"""
    # Check if running as service
    if len(sys.argv) > 1 and sys.argv[1] == '--service':
        run_as_service()
        return
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Allied Telesis Backup Configuration Management Starting")
    logger.info("=" * 60)
    
    # Check for auto-login first (skip service check dialog if auto-login)
    saved_passphrase = get_saved_passphrase()
    
    # Check if service is already running
    service_running = check_service_running()
    if service_running and not saved_passphrase:
        # Only show dialog if NOT auto-login
        logger.info("Background service is already running - GUI will connect to it")
        tk_root = tk.Tk()
        tk_root.withdraw()
        from tkinter import messagebox
        result = messagebox.askyesno(
            "Service Already Running",
            "The backup service is already running in background.\n\n"
            "Do you want to open the GUI to monitor it?\n\n"
            "Note: Scheduled backups will continue running even if you close the GUI.",
            icon='info'
        )
        tk_root.destroy()
        if not result:
            logger.info("User chose not to open GUI")
            return
        logger.info("Opening GUI to monitor running service")
    
    try:
        # Ensure required directories exist
        base_dir = get_base_dir()
        (base_dir / "data").mkdir(exist_ok=True)
        (base_dir / "backups").mkdir(exist_ok=True)
        (base_dir / "logs").mkdir(exist_ok=True)
        
        # Prompt for master passphrase (or auto-login)
        passphrase, auto_login = prompt_master_passphrase()
        if not passphrase:
            logger.error("No passphrase provided")
            sys.exit(1)
        
        if auto_login:
            logger.info("✅ Auto-login enabled - passphrase loaded from saved file")
        
        # Initialize crypto service
        crypto_service = CryptoService(passphrase)
        logger.info("Crypto service initialized")
        
        # Initialize database
        init_db()
        logger.info("Database initialized")
        
        # Always start background services with GUI (for immediate execution and monitoring)
        schedule_service = ScheduleService(crypto_service)
        retention_service = RetentionService()
        started_schedule = False
        started_retention = False
        
        # Auto-start only if no background service is running
        if not service_running:
            schedule_service.start()
            logger.info("✅ Schedule service auto-started with GUI")
            
            retention_service.start()
            logger.info("✅ Retention service auto-started with GUI")
            started_schedule = True
            started_retention = True
        else:
            # Service is detected. If scheduler lock missing or stale (>120s), start GUI scheduler as fallback
            try:
                lock_path = get_base_dir() / "data" / "scheduler.lock"
                stale = False
                if lock_path.exists():
                    try:
                        age = time.time() - lock_path.stat().st_mtime
                        stale = age > 120
                    except Exception:
                        stale = True
                if (not lock_path.exists()) or stale:
                    logger.warning("Service detected but scheduler lock missing/stale. Starting GUI scheduler as fallback.")
                    schedule_service.start()
                    logger.info("✅ Schedule service started by GUI (fallback mode)")
                    retention_service.start()
                    logger.info("✅ Retention service started by GUI (fallback mode)")
                    started_schedule = True
                    started_retention = True
                else:
                    logger.info("Monitor mode: background scheduler detected, GUI will not start its own scheduler")
            except Exception as e:
                logger.warning(f"Fallback scheduler check failed: {e}")
        
        if service_running:
            logger.info("Note: Background service also running (Task Scheduler/Windows Service)")
            logger.info("Both GUI and background services will share the same database")
        
        # Create and run main window
        app = AppWindow(crypto_service, schedule_service, retention_service)
        
        # Set console reference in schedule service for real-time logging
        schedule_service.set_console(app)
        
        logger.info("UI initialized, starting main loop")
        app.run()
        
        # Cleanup on exit - ALWAYS stop GUI services to avoid hidden background processes
        logger.info("Shutting down GUI services")
        if started_schedule:
            schedule_service.stop()
        if started_retention:
            retention_service.stop()
        if service_running:
            logger.info("GUI closed - Background service (Task Scheduler/Windows Service) will handle schedules")
        
    except Exception as e:
        logger.exception("Fatal error in main")
        messagebox.showerror("Fatal Error", f"Application failed to start:\n{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
