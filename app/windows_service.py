"""
Windows Service wrapper for Allied Telesis Backup Configuration Management
This module allows the application to run as a Windows service for auto-startup
"""
import sys
import os
import logging
from pathlib import Path
import time
import servicemanager
import win32serviceutil
import win32service
import win32event

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Ensure service uses the same base dir as GUI/exe if provided via ProgramData override
try:
    program_data = os.environ.get('PROGRAMDATA') or r"C:\\ProgramData"
    override_file = Path(program_data) / "ATBM" / "base_dir.txt"
    if 'ATBM_BASE_DIR' not in os.environ and override_file.exists():
        override_path = override_file.read_text(encoding='utf-8').strip().strip('"').strip("'")
        if override_path:
            os.environ['ATBM_BASE_DIR'] = override_path
            # Can't import logging config yet; basic print as fallback
            try:
                print(f"[ATBM] Using ATBM_BASE_DIR override: {override_path}")
            except Exception:
                pass
except Exception:
    pass

from app.services.crypto_service import CryptoService
from app.services.schedule_service import ScheduleService
from app.services.retention_service import RetentionService
from app.data.db import init_db
from app.config.logging_config import setup_logging
from app.config.paths import get_base_dir


class AlliedTelesisBackupService(win32serviceutil.ServiceFramework):
    """Windows Service wrapper for Allied Telesis Backup application"""
    
    _svc_name_ = "AlliedTelesisBackup"
    _svc_display_name_ = "Allied Telesis Backup Configuration Management"
    _svc_description_ = "Automated backup service for Allied Telesis network switches with scheduled backup execution"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = False
        
        # Setup logging for service
        setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Service components
        self.schedule_service = None
        self.retention_service = None
    
    def SvcStop(self):
        """Stop the service"""
        self.logger.info("Service stop requested")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.is_running = False
    
    def SvcDoRun(self):
        """Start the service"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("Allied Telesis Backup Service Starting")
            self.logger.info("=" * 60)
            
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            
            self.is_running = True
            self.main()
            
        except Exception as e:
            self.logger.exception(f"Service failed to start: {e}")
            servicemanager.LogErrorMsg(f"Service failed: {str(e)}")
    
    def main(self):
        """Main service logic - runs scheduled backups without GUI"""
        try:
            # Ensure service uses the same base dir as GUI/exe if provided via ProgramData override
            try:
                program_data = os.environ.get('PROGRAMDATA') or r"C:\\ProgramData"
                override_file = Path(program_data) / "ATBM" / "base_dir.txt"
                if 'ATBM_BASE_DIR' not in os.environ and override_file.exists():
                    override_path = override_file.read_text(encoding='utf-8').strip().strip('"').strip("'")
                    if override_path:
                        os.environ['ATBM_BASE_DIR'] = override_path
                        self.logger.info(f"Using ATBM_BASE_DIR override: {override_path}")
            except Exception as e:
                self.logger.debug(f"Base dir override check skipped: {e}")

            base_dir = get_base_dir()
            (base_dir / "data").mkdir(parents=True, exist_ok=True)
            (base_dir / "backups").mkdir(parents=True, exist_ok=True)
            (base_dir / "logs").mkdir(parents=True, exist_ok=True)
            
            # Get master passphrase from config file (must be set during installation)
            passphrase_file = base_dir / "data" / ".service_passphrase"
            if not passphrase_file.exists():
                self.logger.error("Master passphrase file not found. Service cannot start.")
                self.logger.error("Please run: install_service.ps1 to configure the service")
                return
            
            with open(passphrase_file, 'r') as f:
                passphrase = f.read().strip()
            
            if not passphrase:
                self.logger.error("Master passphrase is empty. Service cannot start.")
                return
            
            # Initialize crypto service
            crypto_service = CryptoService(passphrase)
            self.logger.info("Crypto service initialized")
            
            # Initialize database
            init_db()
            self.logger.info("Database initialized")
            
            # Start background services
            self.schedule_service = ScheduleService(crypto_service)
            self.schedule_service.start()
            if self.schedule_service.scheduler and self.schedule_service.scheduler.running:
                self.logger.info("Schedule service started")
            else:
                self.logger.warning("Schedule service not running (possibly locked by another instance). Will retry automatically.")
            
            self.retention_service = RetentionService()
            self.retention_service.start()
            self.logger.info("Retention service started")
            
            self.logger.info("Service is now running - monitoring scheduled backups")
            
            # Keep service running until stop is requested
            last_check = time.time()
            while self.is_running:
                # Wait for stop signal (check every 5 seconds)
                rc = win32event.WaitForSingleObject(self.stop_event, 5000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
                # Every 30s, ensure scheduler is running; if not, retry start (e.g., after GUI exit released lock)
                if time.time() - last_check >= 30:
                    last_check = time.time()
                    try:
                        if not (self.schedule_service.scheduler and self.schedule_service.scheduler.running):
                            self.logger.info("Scheduler not running - attempting restart")
                            self.schedule_service.start()
                    except Exception as e:
                        self.logger.warning(f"Scheduler restart attempt failed: {e}")
            
            # Cleanup on stop
            self.logger.info("Shutting down services")
            if self.schedule_service:
                self.schedule_service.stop()
            if self.retention_service:
                self.retention_service.stop()
            
            self.logger.info("Service stopped normally")
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, '')
            )
            
        except Exception as e:
            self.logger.exception("Service error")
            servicemanager.LogErrorMsg(f"Service error: {str(e)}")


def main():
    """Entry point for Windows service"""
    if len(sys.argv) == 1:
        # Called with no arguments - start service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AlliedTelesisBackupService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Called with arguments - handle service management (install, remove, etc.)
        win32serviceutil.HandleCommandLine(AlliedTelesisBackupService)


if __name__ == '__main__':
    main()
