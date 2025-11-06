"""Settings view for application configuration"""
import logging
import os
import sys
from pathlib import Path
from tkinter import END, simpledialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import ntplib
from datetime import datetime
import ctypes
import yaml
from app.config.paths import get_base_dir
from app.config import get_config_path

from app import __version__
from app.services.retention_service import RetentionService
from app.services.crypto_service import CryptoService

logger = logging.getLogger(__name__)


class SettingsView:
    """Application settings view"""
    
    def __init__(self, parent, retention_service: RetentionService, crypto_service: CryptoService):
        self.parent = parent
        self.retention_service = retention_service
        self.crypto = crypto_service
        self.ntp_server = "pool.ntp.org"  # Default NTP server
        
        # Create main frame with scrollbar
        self.frame = ttk.Frame(parent)
        
        # Create canvas and scrollbar
        self.canvas = ttk.Canvas(self.frame)
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, padding=10)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        
        self._create_ui()
    
    def _create_ui(self):
        """Create UI components"""
        # Title
        ttk.Label(
            self.scrollable_frame,
            text="Application Settings",
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(0, 20))
        
        # Retention section
        retention_frame = ttk.LabelFrame(self.scrollable_frame, text="Backup Retention", padding=20)
        retention_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            retention_frame,
            text="Backups are automatically cleaned up after 365 days (1 year).\n"
                 "At least 1 backup per switch is always retained.",
            wraplength=600
        ).pack(pady=10)
        
        ttk.Button(
            retention_frame,
            text="🗑️ Run Cleanup Now",
            command=self._run_cleanup,
            bootstyle=WARNING
        ).pack(pady=10)
        
        # Network settings section
        network_frame = ttk.LabelFrame(self.scrollable_frame, text="Network Settings", padding=20)
        network_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            network_frame,
            text="Connection Timeout: 15 seconds\n"
                 "Read Timeout: 30 seconds\n"
                 "Command Timeout: 60 seconds\n"
                 "Max Retries: 3\n\n"
                 "Edit app/config/appsettings.yaml to customize.",
            wraplength=600,
            bootstyle="secondary"
        ).pack(pady=10)
        
        # Prompt patterns section
        prompt_frame = ttk.LabelFrame(self.scrollable_frame, text="CLI Prompt Patterns", padding=20)
        prompt_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            prompt_frame,
            text="Recognized CLI prompts for ATI switches:",
            wraplength=600
        ).pack(pady=(0, 10))
        
        patterns_text = ttk.Text(prompt_frame, height=6, width=50, state="disabled")
        patterns_text.pack(pady=10)
        
        patterns = [
            "#  - Privileged exec mode",
            ">  - User exec mode",
            "(config)#  - Global configuration mode",
            "(config-if)#  - Interface configuration mode"
        ]
        
        patterns_text.config(state="normal")
        patterns_text.insert("1.0", "\n".join(patterns))
        patterns_text.config(state="disabled")
        
        ttk.Label(
            prompt_frame,
            text="Edit app/config/appsettings.yaml to customize prompt patterns.",
            bootstyle="secondary",
            font=("", 8)
        ).pack()
        
        # Backup Location section
        location_frame = ttk.LabelFrame(self.scrollable_frame, text="📁 Backup Storage Location", padding=20)
        location_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            location_frame,
            text="Configure where backup configurations are saved:",
            wraplength=600
        ).pack(pady=(0, 10))
        
        path_row = ttk.Frame(location_frame)
        path_row.pack(fill=X, pady=10)
        
        ttk.Label(path_row, text="Current Path:", width=15).pack(side=LEFT, padx=5)
        
        # Get current backup path from config
        from pathlib import Path
        import yaml
        from app.config import get_config_path
        
        try:
            config_path = get_config_path()
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            root_folder = Path(config['backup']['root_folder'])
            if not root_folder.is_absolute():
                root_folder = get_base_dir() / root_folder
            current_path = root_folder.resolve()
        except:
            # Fallback to default
            current_path = (get_base_dir() / "backups").resolve()
        
        self.backup_path_var = ttk.StringVar(value=str(current_path))
        
        ttk.Entry(
            path_row,
            textvariable=self.backup_path_var,
            state="readonly",
            width=60
        ).pack(side=LEFT, padx=5, fill=X, expand=YES)
        
        ttk.Button(
            path_row,
            text="📂 Browse",
            command=self._change_backup_location,
            bootstyle=INFO,
            width=12
        ).pack(side=LEFT, padx=5)
        
        ttk.Label(
            location_frame,
            text="Note: Changing the location will move all existing backups to the new location.",
            bootstyle="warning",
            font=("", 8),
            wraplength=600
        ).pack(pady=5)
        
        # Logo Configuration section
        logo_frame = ttk.LabelFrame(self.scrollable_frame, text="🖼️ Logo Configuration", padding=20)
        logo_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            logo_frame,
            text="Configure company and application logos for branding:",
            wraplength=600
        ).pack(pady=(0, 10))
        
        # Company Logo
        company_logo_row = ttk.Frame(logo_frame)
        company_logo_row.pack(fill=X, pady=5)
        
        ttk.Label(company_logo_row, text="Company Logo:", width=15).pack(side=LEFT, padx=5)
        self.company_logo_var = ttk.StringVar(value="Not Set")
        ttk.Entry(
            company_logo_row,
            textvariable=self.company_logo_var,
            state="readonly",
            width=50
        ).pack(side=LEFT, padx=5, fill=X, expand=YES)
        
        ttk.Button(
            company_logo_row,
            text="📂 Browse",
            command=lambda: self._select_logo('company'),
            bootstyle=INFO,
            width=12
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            company_logo_row,
            text="✖ Clear",
            command=lambda: self._clear_logo('company'),
            bootstyle=SECONDARY,
            width=10
        ).pack(side=LEFT, padx=5)
        
        # Application Logo
        app_logo_row = ttk.Frame(logo_frame)
        app_logo_row.pack(fill=X, pady=5)
        
        ttk.Label(app_logo_row, text="Application Logo:", width=15).pack(side=LEFT, padx=5)
        self.app_logo_var = ttk.StringVar(value="Not Set")
        ttk.Entry(
            app_logo_row,
            textvariable=self.app_logo_var,
            state="readonly",
            width=50
        ).pack(side=LEFT, padx=5, fill=X, expand=YES)
        
        ttk.Button(
            app_logo_row,
            text="📂 Browse",
            command=lambda: self._select_logo('application'),
            bootstyle=INFO,
            width=12
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            app_logo_row,
            text="✖ Clear",
            command=lambda: self._clear_logo('application'),
            bootstyle=SECONDARY,
            width=10
        ).pack(side=LEFT, padx=5)
        
        ttk.Label(
            logo_frame,
            text="Supported formats: PNG, JPG, GIF (Recommended: 200x60 pixels for best display)",
            bootstyle="secondary",
            font=("", 8),
            wraplength=600
        ).pack(pady=10)
        
        # Load current logo settings
        self._load_logo_settings()
        
        # Security section
        security_frame = ttk.LabelFrame(self.scrollable_frame, text="🔐 Security", padding=20)
        security_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            security_frame,
            text="Change your master passphrase used to encrypt credentials.\n"
                 "Warning: All existing encrypted credentials will be re-encrypted.",
            wraplength=600
        ).pack(pady=10)
        
        button_frame = ttk.Frame(security_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(
            button_frame,
            text="🔑 Change Master Password",
            command=self._change_master_password,
            bootstyle=WARNING,
            width=25
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="🔥 Factory Reset",
            command=self._factory_reset,
            bootstyle=DANGER,
            width=25
        ).pack(side=LEFT, padx=5)
        
        # Auto-Login section
        autologin_frame = ttk.LabelFrame(self.scrollable_frame, text="🔓 Auto-Login", padding=20)
        autologin_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            autologin_frame,
            text="Enable auto-login to skip passphrase prompt on startup.\n"
                 "⚠️ WARNING: Passphrase will be stored with encryption.\n"
                 "Only enable on trusted computers!",
            wraplength=600
        ).pack(pady=10)
        
        # Check current status
        autologin_status_frame = ttk.Frame(autologin_frame)
        autologin_status_frame.pack(fill=X, pady=10)
        
        self.autologin_status_label = ttk.Label(
            autologin_status_frame,
            text="Status: Checking...",
            font=("Segoe UI", 10)
        )
        self.autologin_status_label.pack(side=LEFT, padx=5)
        
        btn_frame = ttk.Frame(autologin_frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(
            btn_frame,
            text="✅ Enable Auto-Login",
            command=self._enable_autologin,
            bootstyle=SUCCESS
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="❌ Disable Auto-Login",
            command=self._disable_autologin,
            bootstyle=WARNING
        ).pack(side=LEFT, padx=5)
        
        # Update status
        self._check_autologin_status()
        
        # System section
        system_frame = ttk.LabelFrame(self.scrollable_frame, text="⚙️ System - Time Synchronization", padding=20)
        system_frame.pack(fill=X, padx=20, pady=10)
        
        # NTP Server configuration
        ntp_config_frame = ttk.Frame(system_frame)
        ntp_config_frame.pack(fill=X, pady=5)
        
        ttk.Label(ntp_config_frame, text="NTP Server:", width=15).pack(side=LEFT, padx=5)
        self.ntp_server_var = ttk.StringVar(value=self.ntp_server)
        self.ntp_entry = ttk.Entry(ntp_config_frame, textvariable=self.ntp_server_var, width=30)
        self.ntp_entry.pack(side=LEFT, padx=5)
        
        ttk.Label(
            ntp_config_frame,
            text="(e.g., pool.ntp.org, time.google.com)",
            bootstyle="secondary",
            font=("", 8)
        ).pack(side=LEFT, padx=5)
        
        # Current time display
        time_frame = ttk.Frame(system_frame)
        time_frame.pack(fill=X, pady=10)
        
        self.current_time_label = ttk.Label(
            time_frame,
            text=f"Current System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            font=("Consolas", 10)
        )
        self.current_time_label.pack(pady=5)
        
        # Sync button
        ttk.Button(
            system_frame,
            text="🌐 Sync Time with NTP Server",
            command=self._sync_time,
            bootstyle=INFO,
            width=25
        ).pack(pady=10)
        
        ttk.Label(
            system_frame,
            text="Note: Requires administrator privileges on Windows to change system time",
            bootstyle="secondary",
            font=("", 8),
            wraplength=600
        ).pack()
        
        # Auto-Start Service Control section (Task Scheduler)
        service_frame = ttk.LabelFrame(self.scrollable_frame, text="🚀 Auto-Start Service Control", padding=20)
        service_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            service_frame,
            text="Configure automatic startup using Windows Task Scheduler (reliable, no errors!):",
            wraplength=600,
            font=("-size", 10, "-weight", "bold")
        ).pack(pady=(0, 10))
        
        # Task status display
        status_frame = ttk.Frame(service_frame)
        status_frame.pack(fill=X, pady=10)
        
        ttk.Label(status_frame, text="Task Status:", width=15).pack(side=LEFT, padx=5)
        self.task_status_var = ttk.StringVar(value="Checking...")
        self.task_status_label = ttk.Label(
            status_frame,
            textvariable=self.task_status_var,
            font=("Consolas", 10, "bold")
        )
        self.task_status_label.pack(side=LEFT, padx=5)
        
        ttk.Button(
            status_frame,
            text="🔄 Refresh Status",
            command=self._check_task_status,
            bootstyle=SECONDARY,
            width=15
        ).pack(side=LEFT, padx=5)
        
        # Main control buttons
        button_frame = ttk.Frame(service_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(
            button_frame,
            text="📦 Setup Auto-Start",
            command=self._setup_autostart,
            bootstyle=SUCCESS,
            width=20
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="▶️ Start Service Now",
            command=self._start_task_service,
            bootstyle=INFO,
            width=20
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="🗑️ Remove Auto-Start",
            command=self._remove_autostart,
            bootstyle=DANGER,
            width=20
        ).pack(side=LEFT, padx=5)
        
        # Helper buttons
        helper_frame = ttk.Frame(service_frame)
        helper_frame.pack(pady=10)
        
        ttk.Button(
            helper_frame,
            text="📖 View Instructions",
            command=self._show_task_instructions,
            bootstyle=SECONDARY,
            width=20
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            helper_frame,
            text="📂 Open Task Scheduler",
            command=self._open_task_scheduler,
            bootstyle=SECONDARY,
            width=20
        ).pack(side=LEFT, padx=5)
        
        # Info box
        info_frame = ttk.Frame(service_frame)
        info_frame.pack(fill=X, pady=10)
        
        info_text = (
            "✅ Advantages of Task Scheduler:\n"
            "• No Error 1053 issues\n"
            "• More reliable than Windows Service\n"
            "• Auto-starts at Windows boot\n"
            "• Easy to manage\n"
            "• No special permissions needed"
        )
        
        ttk.Label(
            info_frame,
            text=info_text,
            font=("-size", 9),
            foreground="#2E7D32",
            wraplength=600,
            justify=LEFT
        ).pack(side=LEFT, padx=5)
        
        ttk.Label(
            service_frame,
            text="Note: Setup will prompt for master passphrase (one-time setup).",
            bootstyle="secondary",
            font=("", 8),
            wraplength=600
        ).pack(pady=10)
        
        # Check task status on load
        self._check_task_status()
        
        # Application Backup/Restore section
        app_backup_frame = ttk.LabelFrame(self.scrollable_frame, text="💾 Application Configuration Backup/Restore", padding=20)
        app_backup_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            app_backup_frame,
            text="Backup and restore your complete application configuration:\n"
                 "• All switches and credentials\n"
                 "• All backup schedules\n"
                 "• Application settings\n\n"
                 "Note: Backup configurations (files) are NOT included - only database settings.",
            wraplength=600
        ).pack(pady=10)
        
        backup_restore_row = ttk.Frame(app_backup_frame)
        backup_restore_row.pack(pady=10)
        
        ttk.Button(
            backup_restore_row,
            text="💾 Export Configuration",
            command=self._export_app_config,
            bootstyle=SUCCESS,
            width=25
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            backup_restore_row,
            text="📥 Import Configuration",
            command=self._import_app_config,
            bootstyle=INFO,
            width=25
        ).pack(side=LEFT, padx=5)
        
        ttk.Label(
            app_backup_frame,
            text="Export creates a single file with all your settings. Use Import to restore on another machine or after factory reset.",
            bootstyle="secondary",
            font=("", 8),
            wraplength=600
        ).pack()
        
        # About section
        about_frame = ttk.LabelFrame(self.scrollable_frame, text="📖 About", padding=20)
        about_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(
            about_frame,
            text=f"Allied Telesis Backup Configuration Manager v{__version__} (Production)",
            font=("-size", 11, "-weight", "bold"),
            justify=LEFT
        ).pack(anchor=W, pady=(0, 10))
        
        ttk.Label(
            about_frame,
            text="Deskripsi:",
            font=("-size", 10, "-weight", "bold"),
            justify=LEFT
        ).pack(anchor=W, pady=(5, 2))
        
        ttk.Label(
            about_frame,
            text="Platform desktop Windows untuk otomasi backup konfigurasi switch Allied Telesis\n"
                 "yang aman, andal, dan portabel. Dirancang untuk operasi 24/7 dengan monitoring\n"
                 "yang jelas dan jejak audit lengkap.",
            justify=LEFT,
            wraplength=600
        ).pack(anchor=W, padx=(10, 0), pady=(0, 10))
        
        ttk.Label(
            about_frame,
            text="Fitur Utama:",
            font=("-size", 10, "-weight", "bold"),
            justify=LEFT
        ).pack(anchor=W, pady=(5, 2))
        
        ttk.Label(
            about_frame,
            text="• Automated scheduling & background service (Windows Service/Task Scheduler)\n"
                 "• Encrypted credential vault (Fernet) & centralized logging\n"
                 "• SSH & Telnet with retry, configuration diff, and retention policy",
            justify=LEFT,
            wraplength=600
        ).pack(anchor=W, padx=(10, 0), pady=(0, 10))
        
        ttk.Label(
            about_frame,
            text="Detail Teknis:",
            font=("-size", 10, "-weight", "bold"),
            justify=LEFT
        ).pack(anchor=W, pady=(5, 2))
        
        ttk.Label(
            about_frame,
            text=f"Versi: {__version__} (Production)\n"
                 "Teknologi: Python 3, ttkbootstrap, APScheduler, SQLAlchemy, Paramiko\n"
                 "Pengembang: Yohanes Octavian Rizky\n"
                 "Tahun: 2025",
            justify=LEFT,
            wraplength=600
        ).pack(anchor=W, padx=(10, 0), pady=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(about_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(
            button_frame,
            text="📄 Open Log Folder",
            command=self._open_logs,
            bootstyle=INFO,
            width=20
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="📚 View History",
            command=self._show_history,
            bootstyle=PRIMARY,
            width=20
        ).pack(side=LEFT, padx=5)
    
    def _run_cleanup(self):
        """Run retention cleanup now"""
        if not Messagebox.show_question(
            "This will delete backups older than 365 days (1 year).\nContinue?",
            "Confirm Cleanup"
        ):
            return
        
        try:
            self.retention_service.cleanup_now()
            Messagebox.show_info("Cleanup completed. Check logs for details.", "Success")
        except Exception as e:
            Messagebox.show_error(f"Cleanup failed: {e}", "Error")
            logger.exception("Manual cleanup failed")
    
    def _change_backup_location(self):
        """Change the backup storage location"""
        from tkinter import filedialog
        from pathlib import Path
        import shutil
        import yaml
        from app.config import get_config_path
        
        # Get current backup path from config
        try:
            config_path = get_config_path()
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            root_folder = Path(config['backup']['root_folder'])
            if not root_folder.is_absolute():
                root_folder = get_base_dir() / root_folder
            current_path = root_folder.resolve()
        except:
            current_path = (get_base_dir() / "backups").resolve()
        
        # Ask user to select new directory
        new_path = filedialog.askdirectory(
            title="Select Backup Storage Location",
            initialdir=str(current_path.parent)
        )
        
        if not new_path:
            return  # User cancelled
        
        new_path = Path(new_path)
        
        # Check if same location
        if new_path.resolve() == current_path.resolve():
            Messagebox.show_info("This is already the current backup location.", "No Change")
            return
        
        # Check if new path is inside current path or vice versa
        try:
            # Check if new_path is a subdirectory of current_path
            new_path.resolve().relative_to(current_path.resolve())
            Messagebox.show_error(
                f"Cannot move backup folder into itself!\n\n"
                f"New location cannot be inside the current backup folder.\n\n"
                f"Current: {current_path}\n"
                f"Selected: {new_path}",
                "Invalid Location"
            )
            return
        except ValueError:
            # Not a subdirectory, this is fine
            pass
        
        try:
            # Check if current_path is a subdirectory of new_path
            current_path.resolve().relative_to(new_path.resolve())
            Messagebox.show_error(
                f"Cannot select parent directory of current backup folder!\n\n"
                f"This would create a circular move operation.\n\n"
                f"Current: {current_path}\n"
                f"Selected: {new_path}",
                "Invalid Location"
            )
            return
        except ValueError:
            # Not a parent directory, this is fine
            pass
        
        # Confirm the change
        if not Messagebox.show_question(
            f"Move all backups from:\n{current_path}\n\nTo:\n{new_path}\n\n"
            f"This operation may take some time. Continue?",
            "Confirm Location Change"
        ):
            return
        
        try:
            # Create new location if it doesn't exist
            new_path.mkdir(parents=True, exist_ok=True)
            
            # Check if current backups exist
            if current_path.exists() and any(current_path.iterdir()):
                # Move all backups to new location
                for item in current_path.iterdir():
                    dest = new_path / item.name
                    if dest.exists():
                        Messagebox.show_error(
                            f"Destination already contains: {item.name}\n"
                            f"Please choose an empty directory.",
                            "Location Error"
                        )
                        return
                    shutil.move(str(item), str(dest))
                
                logger.info(f"Moved backups from {current_path} to {new_path}")
            
            # Update database backup paths
            from app.data.repository import Repository
            updated_count = 0
            try:
                with Repository() as repo:
                    backups = repo.list_backups()
                    for backup in backups:
                        old_file_path = Path(backup.file_path)
                        # Check if path starts with old location
                        try:
                            relative_path = old_file_path.relative_to(current_path)
                            # Update to new path
                            new_file_path = new_path / relative_path
                            backup.file_path = str(new_file_path)
                            updated_count += 1
                        except ValueError:
                            # Path doesn't start with current_path, skip
                            pass
                    repo.session.commit()
                logger.info(f"Updated {updated_count} backup paths in database")
            except Exception as e:
                logger.error(f"Failed to update database paths: {e}")
                # Continue anyway, user can manually fix if needed
            
            # Update config file
            import yaml
            from app.config import get_config_path
            config_path = get_config_path()
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            config['backup']['root_folder'] = str(new_path)
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            # Update display
            self.backup_path_var.set(str(new_path))
            
            Messagebox.show_info(
                f"Backup location changed successfully!\n\n"
                f"New location: {new_path}\n"
                f"Updated {updated_count} backup records in database\n\n"
                f"Changes take effect immediately for manual and scheduled backups.",
                "Success"
            )
            logger.info(f"Backup location changed to: {new_path}, updated {updated_count} database records")
            
        except Exception as e:
            Messagebox.show_error(
                f"Failed to change backup location: {str(e)}",
                "Error"
            )
            logger.exception("Failed to change backup location")
    
    def _change_master_password(self):
        """Change the master password and re-encrypt all credentials"""
        from app.data.repository import Repository
        from tkinter import Toplevel
        
        # Create custom dialog
        dialog = Toplevel(self.parent)
        dialog.title("Change Master Password")
        dialog.geometry("500x300")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (300 // 2)
        dialog.geometry(f"500x300+{x}+{y}")
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=BOTH, expand=True)
        
        # Title
        ttk.Label(
            main_frame,
            text="Change Master Password",
            font=("Segoe UI", 12, "bold")
        ).pack(pady=(0, 20))
        
        # Current password
        ttk.Label(main_frame, text="Current Password:").pack(anchor=W, pady=(0, 5))
        current_pass_var = ttk.StringVar()
        current_pass_entry = ttk.Entry(main_frame, textvariable=current_pass_var, show="*", width=40)
        current_pass_entry.pack(pady=(0, 15))
        current_pass_entry.focus()
        
        # New password
        ttk.Label(main_frame, text="New Password (min 8 characters):").pack(anchor=W, pady=(0, 5))
        new_pass_var = ttk.StringVar()
        new_pass_entry = ttk.Entry(main_frame, textvariable=new_pass_var, show="*", width=40)
        new_pass_entry.pack(pady=(0, 15))
        
        # Confirm password
        ttk.Label(main_frame, text="Confirm New Password:").pack(anchor=W, pady=(0, 5))
        confirm_pass_var = ttk.StringVar()
        confirm_pass_entry = ttk.Entry(main_frame, textvariable=confirm_pass_var, show="*", width=40)
        confirm_pass_entry.pack(pady=(0, 20))
        
        result = {'success': False}
        
        def on_submit():
            current_password = current_pass_var.get()
            new_password = new_pass_var.get()
            confirm_password = confirm_pass_var.get()
            
            # Validation
            if not current_password:
                Messagebox.show_error("Please enter current password", "Validation Error")
                return
            
            if not new_password:
                Messagebox.show_error("Please enter new password", "Validation Error")
                return
            
            if len(new_password) < 8:
                Messagebox.show_error(
                    "Password must be at least 8 characters long",
                    "Invalid Password"
                )
                return
            
            if new_password != confirm_password:
                Messagebox.show_error(
                    "Passwords do not match!",
                    "Confirmation Failed"
                )
                return
            
            # Verify current password by creating test CryptoService
            try:
                test_crypto = CryptoService(current_password)
            except ValueError:
                Messagebox.show_error(
                    "Current password is incorrect!",
                    "Authentication Failed"
                )
                return
            except Exception as e:
                Messagebox.show_error(
                    f"Password verification failed: {e}",
                    "Error"
                )
                return
            
            # Re-encrypt all credentials and update master.key
            try:
                import os
                
                with Repository() as repo:
                    creds = repo.list_credentials()
                    
                    # Delete old master.key to create new one with new password
                    master_key_file = "data/master.key"
                    if os.path.exists(master_key_file):
                        os.remove(master_key_file)
                    
                    # Create new crypto service with new password (will create new master.key)
                    new_crypto = CryptoService(new_password)
                    
                    # Re-encrypt all credentials if any exist
                    if creds:
                        for cred in creds:
                            cred_data = self.crypto.decrypt_credential(cred.enc_blob)
                            new_blob = new_crypto.encrypt_credential(
                                cred_data['username'],
                                cred_data['password'],
                                cred_data.get('enable_password', '')
                            )
                            repo.update_credential(cred.id, enc_blob=new_blob)
                    
                    # Update the crypto service
                    self.crypto = new_crypto
                    
                    result['success'] = True
                    result['count'] = len(creds)
                    dialog.destroy()
                    
            except Exception as e:
                Messagebox.show_error(
                    f"Failed to change password: {e}",
                    "Error"
                )
                logger.exception("Failed to change master password")
        
        def on_cancel():
            dialog.destroy()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Change Password",
            command=on_submit,
            bootstyle=SUCCESS,
            width=18
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=on_cancel,
            bootstyle=SECONDARY,
            width=18
        ).pack(side=LEFT, padx=5)
        
        # Bind Enter key
        dialog.bind('<Return>', lambda e: on_submit())
        dialog.bind('<Escape>', lambda e: on_cancel())
        
        # Wait for dialog to close
        dialog.wait_window()
        
        # Show success message
        if result['success']:
            if result['count'] > 0:
                msg = (
                    f"Master password changed successfully!\n"
                    f"Re-encrypted {result['count']} credential(s).\n\n"
                    f"Please restart the application and use your new password."
                )
            else:
                msg = (
                    "Master password changed successfully!\n\n"
                    "Please restart the application and use your new password."
                )
            
            Messagebox.show_info(msg, "Success")
            logger.info(f"Master password changed, re-encrypted {result['count']} credentials")
    
    def _factory_reset(self):
        """Factory reset - delete all data"""
        from app.data.repository import Repository
        import os
        
        # Simple Yes/No confirmation using Messagebox
        confirmed = Messagebox.show_question(
            "⚠️ FACTORY RESET WARNING\n\n"
            "This will permanently delete ALL data:\n"
            "• All switches\n"
            "• All credentials\n"
            "• All backup history\n"
            "• All schedules\n\n"
            "This action CANNOT be undone!\n\n"
            "Are you sure you want to reset everything?",
            "Factory Reset Confirmation",
            buttons=["Yes:danger", "No:secondary"]
        )
        
        if confirmed == "Yes":
            try:
                # Delete database file
                base_dir = get_base_dir()
                db_file = base_dir / "data" / "app.db"
                if db_file.exists():
                    os.remove(db_file)
                    logger.info("Factory reset: Database deleted")
                
                # Also check for old name
                old_db_file = base_dir / "data" / "backups.db"
                if old_db_file.exists():
                    os.remove(old_db_file)
                    logger.info("Factory reset: Old database deleted")
                
                # Delete master.key
                master_key_file = base_dir / "data" / "master.key"
                if master_key_file.exists():
                    os.remove(master_key_file)
                    logger.info("Factory reset: Master key deleted")
                
                # Delete backup files
                backup_dir = base_dir / "backups"
                if backup_dir.exists():
                    import shutil
                    shutil.rmtree(str(backup_dir))
                    logger.info("Factory reset: Backup directory deleted")
                
                Messagebox.show_info(
                    "Factory reset completed successfully!\n\n"
                    "All data has been deleted.\n"
                    "Please restart the application.",
                    "Reset Complete"
                )
                
                logger.warning("Factory reset performed - all data deleted")
                
            except Exception as e:
                Messagebox.show_error(
                    f"Factory reset failed: {e}",
                    "Error"
                )
                logger.exception("Factory reset failed")
    
    def _export_app_config(self):
        """Export complete application configuration"""
        from tkinter import filedialog
        from datetime import datetime
        import json
        import base64
        from app.data.repository import Repository
        
        # Ask where to save
        filename = filedialog.asksaveasfilename(
            title="Export Application Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"app_config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        if not filename:
            return
        
        try:
            config_data = {
                'export_date': datetime.now().isoformat(),
                'app_version': '3.0',
                'switches': [],
                'credentials': [],
                'schedules': [],
                'settings': {}
            }
            
            with Repository() as repo:
                # Export credentials
                credentials = repo.list_credentials()
                logger.info(f"Exporting {len(credentials)} credentials")
                for cred in credentials:
                    config_data['credentials'].append({
                        'name': cred.name,
                        'enc_blob': base64.b64encode(cred.enc_blob).decode('utf-8')  # Encode bytes to base64 string
                    })
                logger.info(f"Credentials exported: {[c['name'] for c in config_data['credentials']]}")
                
                # Export switches
                switches = repo.list_switches()
                for switch in switches:
                    config_data['switches'].append({
                        'name': switch.name,
                        'ip': switch.ip,
                        'protocol': switch.protocol,
                        'port': switch.port,
                        'credential_name': switch.credential.name,
                        'notes': switch.notes
                    })
                
                # Export schedules
                jobs = repo.list_jobs()
                for job in jobs:
                    config_data['schedules'].append({
                        'switch_name': job.switch.name,
                        'interval_minutes': job.interval_minutes,
                        'enabled': job.enabled,
                        'schedule_hour': getattr(job, 'schedule_hour', 8),
                        'schedule_minute': getattr(job, 'schedule_minute', 0)
                    })
            
            # Export settings from config file
            import yaml
            from app.config import get_config_path
            config_path = get_config_path()
            with open(config_path, 'r') as f:
                app_settings = yaml.safe_load(f)
            config_data['settings'] = app_settings
            
            # Save to file
            with open(filename, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            Messagebox.show_info(
                f"Configuration exported successfully!\n\n"
                f"File: {filename}\n\n"
                f"Exported:\n"
                f"• {len(config_data['credentials'])} credentials\n"
                f"• {len(config_data['switches'])} switches\n"
                f"• {len(config_data['schedules'])} schedules",
                "Export Complete"
            )
            logger.info(f"Application configuration exported to: {filename}")
            
        except Exception as e:
            Messagebox.show_error(f"Export failed: {str(e)}", "Error")
            logger.exception("Configuration export failed")
    
    def _import_app_config(self):
        """Import complete application configuration"""
        from tkinter import filedialog
        import json
        import base64
        from app.data.repository import Repository
        
        # Confirm import
        if not Messagebox.show_question(
            "Importing configuration will ADD to existing data.\n\n"
            "To replace all data, use Factory Reset first.\n\n"
            "Continue with import?",
            "Confirm Import"
        ):
            return
        
        # Ask for file
        filename = filedialog.askopenfilename(
            title="Import Application Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            # Load configuration file
            with open(filename, 'r') as f:
                config_data = json.load(f)
            
            imported_counts = {
                'credentials': 0,
                'switches': 0,
                'schedules': 0
            }
            
            import_errors = []  # Collect errors to show at end
            
            # Collect all data to import
            cred_map = {}  # Map old names to new IDs
            switch_map = {}  # Map old names to new IDs
            schedule_list = []  # List of schedules to import
            
            # First pass: Import credentials and switches using Repository
            with Repository() as repo:
                # Import credentials first (switches need them)
                for cred_data in config_data.get('credentials', []):
                    # Validate credential data
                    if not cred_data.get('name') or not cred_data.get('name').strip():
                        logger.warning("Skipping credential with blank name")
                        continue
                    
                    if not cred_data.get('enc_blob'):
                        logger.warning(f"Skipping credential '{cred_data.get('name')}' with blank encrypted data")
                        continue
                    
                    # Check if credential already exists
                    existing = repo.get_credential_by_name(cred_data['name'])
                    if existing:
                        cred_map[cred_data['name']] = existing.id
                        logger.info(f"Credential '{cred_data['name']}' already exists, skipping")
                        continue
                    
                    # Create new credential - import as-is
                    # If encrypted with different password, import anyway (will show [Error] in credentials view)
                    try:
                        enc_blob = base64.b64decode(cred_data['enc_blob'])
                        
                        # Try to decrypt with current password to verify it works
                        can_decrypt = False
                        try:
                            test_data = self.crypto.decrypt_credential(enc_blob)
                            # If decrypt succeeds, re-encrypt with current password to ensure compatibility
                            enc_blob = self.crypto.encrypt_credential(
                                test_data['username'],
                                test_data['password'],
                                test_data.get('enable_password', '')
                            )
                            logger.info(f"Credential '{cred_data['name']}' re-encrypted with current master password")
                            can_decrypt = True
                        except Exception as decrypt_error:
                            # Decrypt failed - import as-is, will show [Error] in credentials view
                            logger.warning(f"Cannot decrypt credential '{cred_data['name']}' with current password: {decrypt_error}")
                            logger.info(f"Importing credential '{cred_data['name']}' as-is (will show [Error] until re-entered)")
                            error_msg = f"Credential '{cred_data.get('name')}': Encrypted with different password - imported but needs re-entry"
                            import_errors.append(error_msg)
                            # Keep original enc_blob, import anyway
                        
                        new_cred = repo.create_credential(
                            name=cred_data['name'],
                            enc_blob=enc_blob
                        )
                        cred_map[cred_data['name']] = new_cred.id
                        imported_counts['credentials'] += 1
                    except Exception as e:
                        error_msg = f"Credential '{cred_data.get('name')}': {str(e)}"
                        logger.error(f"Failed to import {error_msg}")
                        import_errors.append(error_msg)
                        continue
                
                # Import switches
                for switch_data in config_data.get('switches', []):
                    # Check if switch already exists
                    switches = repo.list_switches()
                    existing = next((s for s in switches if s.name == switch_data['name']), None)
                    if existing:
                        switch_map[switch_data['name']] = existing.id
                        logger.info(f"Switch '{switch_data['name']}' already exists, skipping")
                        continue
                    
                    # Get credential ID
                    cred_id = cred_map.get(switch_data['credential_name'])
                    if not cred_id:
                        logger.warning(f"Credential '{switch_data['credential_name']}' not found for switch '{switch_data['name']}', skipping switch")
                        continue
                    
                    # Create new switch
                    new_switch = repo.create_switch(
                        name=switch_data['name'],
                        ip=switch_data['ip'],
                        protocol=switch_data['protocol'],
                        port=switch_data['port'],
                        credential_id=cred_id,
                        notes=switch_data.get('notes')
                    )
                    switch_map[switch_data['name']] = new_switch.id
                    imported_counts['switches'] += 1
                
                # Import schedules and collect job IDs
                for schedule_data in config_data.get('schedules', []):
                    # Get switch ID
                    switch_id = switch_map.get(schedule_data['switch_name'])
                    if not switch_id:
                        logger.warning(f"Switch '{schedule_data['switch_name']}' not found for schedule, skipping")
                        continue
                    
                    # Check if schedule already exists
                    jobs = repo.list_jobs()
                    existing = next((j for j in jobs if j.switch_id == switch_id and j.interval_minutes == schedule_data['interval_minutes']), None)
                    if existing:
                        logger.info(f"Schedule for '{schedule_data['switch_name']}' already exists, skipping")
                        continue
                    
                    # Create new schedule
                    job = repo.create_job(
                        switch_id=switch_id,
                        interval_minutes=schedule_data['interval_minutes'],
                        enabled=schedule_data.get('enabled', True)
                    )
                    
                    # Store for later SQL update
                    schedule_list.append({
                        'job_id': job.id,
                        'schedule_hour': schedule_data.get('schedule_hour', 8),
                        'schedule_minute': schedule_data.get('schedule_minute', 0)
                    })
                    imported_counts['schedules'] += 1
            
            # Second pass: Update schedule times with direct SQL (after Repository is closed)
            if schedule_list:
                import sqlite3
                base_dir = get_base_dir()
                db_path = base_dir / "data" / "app.db"
                conn = sqlite3.connect(str(db_path.absolute()))
                try:
                    cursor = conn.cursor()
                    for schedule_info in schedule_list:
                        cursor.execute(
                            "UPDATE jobs SET schedule_hour = ?, schedule_minute = ? WHERE id = ?",
                            (schedule_info['schedule_hour'], schedule_info['schedule_minute'], schedule_info['job_id'])
                        )
                    conn.commit()
                finally:
                    conn.close()
            
            # Show results
            message = f"Configuration imported!\n\n"
            message += f"Imported:\n"
            message += f"• {imported_counts['credentials']} credentials\n"
            message += f"• {imported_counts['switches']} switches\n"
            message += f"• {imported_counts['schedules']} schedules\n\n"
            
            if import_errors:
                message += f"⚠️ Warnings ({len(import_errors)}):\n"
                for error in import_errors[:3]:  # Show first 3 errors
                    message += f"• {error}\n"
                if len(import_errors) > 3:
                    message += f"• ... and {len(import_errors) - 3} more\n"
                message += f"\n"
                message += f"ℹ️ Credentials encrypted with different password were imported\n"
                message += f"but will show [Error]. Please edit them to re-enter passwords.\n\n"
            
            message += f"Please restart the application for schedules to activate."
            
            if import_errors:
                Messagebox.show_warning(message, "Import Complete (with errors)")
            else:
                Messagebox.show_info(message, "Import Complete")
            
            logger.info(f"Application configuration imported from: {filename}")
            
        except Exception as e:
            Messagebox.show_error(f"Import failed: {str(e)}", "Error")
            logger.exception("Configuration import failed")
    
    def _load_logo_settings(self):
        """Load logo settings from config file"""
        try:
            import yaml
            from app.config import get_config_path
            
            config_path = get_config_path()
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                # Load logo paths if they exist
                if 'branding' in config:
                    company_logo = config['branding'].get('company_logo', 'Not Set')
                    app_logo = config['branding'].get('application_logo', 'Not Set')
                    
                    self.company_logo_var.set(company_logo if company_logo else 'Not Set')
                    self.app_logo_var.set(app_logo if app_logo else 'Not Set')
        except Exception as e:
            logger.warning(f"Failed to load logo settings: {e}")
    
    def _select_logo(self, logo_type: str):
        """Select logo file"""
        from tkinter import filedialog
        import yaml
        from app.config import get_config_path
        
        filename = filedialog.askopenfilename(
            title=f"Select {logo_type.title()} Logo",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("GIF files", "*.gif"),
                ("All files", "*.*")
            ]
        )
        
        if not filename:
            return
        
        try:
            # Update config file
            config_path = get_config_path()
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if 'branding' not in config:
                config['branding'] = {}
            
            if logo_type == 'company':
                config['branding']['company_logo'] = filename
                self.company_logo_var.set(filename)
            else:
                config['branding']['application_logo'] = filename
                self.app_logo_var.set(filename)
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            Messagebox.show_info(
                f"{logo_type.title()} logo updated successfully!\n\n"
                f"File: {filename}\n\n"
                f"Restart the application to see the changes.",
                "Logo Updated"
            )
            logger.info(f"{logo_type} logo set to: {filename}")
            
        except Exception as e:
            Messagebox.show_error(f"Failed to save logo: {str(e)}", "Error")
            logger.exception("Logo save failed")
    
    def _clear_logo(self, logo_type: str):
        """Clear logo setting"""
        import yaml
        from app.config import get_config_path
        
        try:
            config_path = get_config_path()
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if 'branding' in config:
                if logo_type == 'company':
                    config['branding']['company_logo'] = None
                    self.company_logo_var.set('Not Set')
                else:
                    config['branding']['application_logo'] = None
                    self.app_logo_var.set('Not Set')
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            Messagebox.show_info(
                f"{logo_type.title()} logo cleared.\n\n"
                f"Restart the application to see the changes.",
                "Logo Cleared"
            )
            logger.info(f"{logo_type} logo cleared")
            
        except Exception as e:
            Messagebox.show_error(f"Failed to clear logo: {str(e)}", "Error")
            logger.exception("Logo clear failed")
    
    def _sync_time(self):
        """Sync system time with NTP server"""
        # Get NTP server from entry field
        ntp_server = self.ntp_server_var.get().strip()
        
        if not ntp_server:
            Messagebox.show_error("Please enter an NTP server address", "No Server")
            return
        
        try:
            # Get time from NTP server
            logger.info(f"Contacting NTP server: {ntp_server}")
            ntp_client = ntplib.NTPClient()
            response = ntp_client.request(ntp_server, version=3, timeout=5)
            
            ntp_time = datetime.fromtimestamp(response.tx_time)
            
            # Update the display
            self.current_time_label.config(
                text=f"NTP Server Time: {ntp_time.strftime('%Y-%m-%d %H:%M:%S')} (from {ntp_server})"
            )
            
            # Try to set system time (Windows only, requires admin)
            try:
                # Set system time using Windows API
                class SYSTEMTIME(ctypes.Structure):
                    _fields_ = [
                        ('wYear', ctypes.c_uint16),
                        ('wMonth', ctypes.c_uint16),
                        ('wDayOfWeek', ctypes.c_uint16),
                        ('wDay', ctypes.c_uint16),
                        ('wHour', ctypes.c_uint16),
                        ('wMinute', ctypes.c_uint16),
                        ('wSecond', ctypes.c_uint16),
                        ('wMilliseconds', ctypes.c_uint16),
                    ]
                
                system_time = SYSTEMTIME()
                system_time.wYear = ntp_time.year
                system_time.wMonth = ntp_time.month
                system_time.wDayOfWeek = ntp_time.weekday()
                system_time.wDay = ntp_time.day
                system_time.wHour = ntp_time.hour
                system_time.wMinute = ntp_time.minute
                system_time.wSecond = ntp_time.second
                system_time.wMilliseconds = int(ntp_time.microsecond / 1000)
                
                # Set system time
                result = ctypes.windll.kernel32.SetSystemTime(ctypes.byref(system_time))
                
                if result:
                    Messagebox.show_info(
                        f"System time synchronized successfully!\n\n"
                        f"Server: {ntp_server}\n"
                        f"New time: {ntp_time.strftime('%Y-%m-%d %H:%M:%S')}",
                        "Time Sync Success"
                    )
                    logger.info(f"System time synced with NTP: {ntp_time} from {ntp_server}")
                    
                    # Update display with current time
                    self.current_time_label.config(
                        text=f"Current System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                else:
                    Messagebox.show_warning(
                        f"Retrieved time from {ntp_server}:\n"
                        f"{ntp_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"Could not set system time.\n"
                        f"Please run the application as Administrator.",
                        "Permission Required"
                    )
                    
            except Exception as set_error:
                logger.error(f"Failed to set system time: {set_error}")
                Messagebox.show_warning(
                    f"Retrieved time from {ntp_server}:\n"
                    f"{ntp_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"Could not update system time.\n"
                    f"Run as Administrator to set system time.",
                    "Permission Required"
                )
                
        except Exception as e:
            Messagebox.show_error(
                f"Failed to sync time with NTP server '{ntp_server}':\n{e}\n\n"
                f"Check server address and internet connection.",
                "Time Sync Failed"
            )
            logger.exception(f"NTP time sync failed with server {ntp_server}")
    
    def _open_logs(self):
        """Open logs folder"""
        try:
            import subprocess
            from pathlib import Path
            
            base_dir = get_base_dir()
            log_folder = (base_dir / "logs").absolute()
            if not log_folder.exists():
                Messagebox.show_error("Logs folder not found", "Error")
                return
            
            subprocess.Popen(f'explorer "{log_folder}"')
        except Exception as e:
            Messagebox.show_error(f"Failed to open logs folder: {e}", "Error")
    
    def _show_history(self):
        """Show application development history from memory.md"""
        from tkinter import Toplevel, Text, Scrollbar
        import tkinter as tk
        from pathlib import Path
        import sys
        
        try:
            # Handle PyInstaller frozen executable path
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                base_path = Path(sys._MEIPASS)
                memory_file = base_path / "memory.md"
            else:
                # Running as script
                memory_file = Path("memory.md")
            
            if not memory_file.exists():
                Messagebox.show_error(
                    "History file (memory.md) not found.\n\n"
                    "This file contains the development history and changelog.",
                    "File Not Found"
                )
                return
            
            with open(memory_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Create history window
            history_window = Toplevel(self.parent)
            history_window.title("Application Development History")
            history_window.geometry("900x700")
            history_window.transient(self.parent)
            
            # Center window
            history_window.update_idletasks()
            x = (history_window.winfo_screenwidth() // 2) - (450)
            y = (history_window.winfo_screenheight() // 2) - (350)
            history_window.geometry(f"900x700+{x}+{y}")
            
            # Main frame
            main_frame = ttk.Frame(history_window, padding=10)
            main_frame.pack(fill=BOTH, expand=True)
            
            # Title
            ttk.Label(
                main_frame,
                text="📚 Application Development History",
                font=("-size", 14, "-weight", "bold")
            ).pack(pady=(0, 10))
            
            # Text widget with scrollbar
            text_frame = ttk.Frame(main_frame)
            text_frame.pack(fill=BOTH, expand=True)
            
            scrollbar = Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            text_widget = Text(
                text_frame,
                wrap="word",
                yscrollcommand=scrollbar.set,
                font=("Consolas", 9),
                padx=10,
                pady=10
            )
            text_widget.pack(side=tk.LEFT, fill=BOTH, expand=True)
            scrollbar.config(command=text_widget.yview)
            
            # Insert content
            text_widget.insert("1.0", content)
            text_widget.config(state="disabled")
            
            # Close button
            ttk.Button(
                main_frame,
                text="Close",
                command=history_window.destroy,
                bootstyle=SECONDARY,
                width=15
            ).pack(pady=(10, 0))
            
        except Exception as e:
            Messagebox.show_error(
                f"Failed to load history:\n\n{str(e)}",
                "Error"
            )
            logger.exception("Failed to show history")
    
    def _check_task_status(self):
        """Check if auto-start task is configured"""
        import subprocess
        
        try:
            # Check if task exists
            result = subprocess.run(
                ['schtasks', '/Query', '/TN', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                if 'ready' in output or 'running' in output:
                    self.task_status_var.set("✅ Configured")
                    self.task_status_label.config(bootstyle="success")
                elif 'disabled' in output:
                    self.task_status_var.set("⏸️ Disabled")
                    self.task_status_label.config(bootstyle="warning")
                else:
                    self.task_status_var.set("❓ Unknown")
                    self.task_status_label.config(bootstyle="secondary")
            else:
                self.task_status_var.set("❌ Not Setup")
                self.task_status_label.config(bootstyle="secondary")
                
        except Exception as e:
            self.task_status_var.set("❌ Not Setup")
            self.task_status_label.config(bootstyle="secondary")
            logger.debug(f"Task status check: {e}")
    
    def _setup_autostart(self):
        """Setup auto-start using Task Scheduler"""
        import subprocess
        from pathlib import Path
        from tkinter import simpledialog
        
        # Check if already setup
        result = subprocess.run(
            ['schtasks', '/Query', '/TN', 'AlliedTelesisBackup'],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            if not Messagebox.show_question(
                "Auto-start is already configured.\n\n"
                "Do you want to reconfigure it?",
                "Already Setup"
            ):
                return
            # Delete existing task
            subprocess.run(
                ['schtasks', '/Delete', '/TN', 'AlliedTelesisBackup', '/F'],
                capture_output=True,
                timeout=5
            )
        
        # Confirm setup
        if not Messagebox.show_question(
            "Setup Auto-Start with Task Scheduler?\n\n"
            "⚠️ IMPORTANT: Requires Administrator privileges!\n\n"
            "This will:\n"
            "• Create a Windows Scheduled Task (SYSTEM account)\n"
            "• Auto-start backup service at Windows boot\n"
            "• Run 24/7 in background (no window)\n"
            "• Independent from GUI (can close anytime)\n"
            "• Require master passphrase (one-time)\n\n"
            "Note: You must run this application as Administrator!\n\n"
            "Continue?",
            "Confirm Setup (Admin Required)"
        ):
            return
        
        # Get master passphrase
        passphrase = simpledialog.askstring(
            "Master Passphrase",
            "Enter the master passphrase for credential encryption:",
            show='*'
        )
        
        if not passphrase:
            Messagebox.show_warning("Setup cancelled - passphrase required", "Cancelled")
            return
        
        if len(passphrase) < 8:
            Messagebox.show_error(
                "Passphrase must be at least 8 characters long",
                "Invalid Passphrase"
            )
            return
        
        try:
            # Save passphrase under app base dir
            base_dir = get_base_dir()
            data_dir = base_dir / "data"
            data_dir.mkdir(exist_ok=True)
            passphrase_file = data_dir / ".service_passphrase"
            with open(passphrase_file, 'w', encoding='utf-8') as f:
                f.write(passphrase)
            
            # Persist base_dir override for Task Scheduler via ProgramData
            try:
                program_data = os.environ.get('PROGRAMDATA') or r"C:\\ProgramData"
                atbm_dir = Path(program_data) / "ATBM"
                atbm_dir.mkdir(parents=True, exist_ok=True)
                override_file = atbm_dir / "base_dir.txt"
                # Use exe directory when frozen, otherwise current base_dir
                if getattr(sys, 'frozen', False):
                    exe_dir = Path(sys.executable).parent
                    override_path = exe_dir
                else:
                    override_path = base_dir
                override_file.write_text(str(override_path), encoding='utf-8')
                logger.info(f"Wrote base_dir override to {override_file}: {override_path}")
            except Exception as e:
                logger.warning(f"Failed to write ProgramData base_dir override: {e}")
            
            # Build task action (TR) with base dir override to ensure same DB/config
            exe_path = sys.executable
            if getattr(sys, 'frozen', False):
                exe_dir = Path(exe_path).parent
                # Use cmd to set env var with safe quoting then launch
                tr_action = f'cmd.exe /c "set \"ATBM_BASE_DIR={exe_dir}\" && \"{exe_path}\" --service"'
            else:
                script_path = (base_dir / 'app' / 'main.py').absolute()
                # Use current base_dir for source runs with safe quoting
                tr_action = f'cmd.exe /c "set \"ATBM_BASE_DIR={base_dir}\" && \"{exe_path}\" -u \"{script_path}\" --service"'
            
            # Determine run account (SYSTEM by default). If UNC share is configured as backup root,
            # recommend running under a user account for network access.
            run_args = ['/RU', 'SYSTEM']
            try:
                cfg_path = get_config_path()
                with open(cfg_path, 'r') as cf:
                    cfg = yaml.safe_load(cf)
                root_folder = str(cfg.get('backup', {}).get('root_folder', '') or '')
                if root_folder.startswith('\\\\'):
                    if Messagebox.show_question(
                        "Detected network share (UNC) as backup destination.\n\n"
                        "Windows SYSTEM account typically cannot access network shares.\n\n"
                        "Do you want to run the background task under your user account instead?",
                        "Use User Account for Network Share?"
                    ):
                        default_user = os.getlogin()
                        username = simpledialog.askstring("Windows Username", "Enter DOMAIN\\User or User:", initialvalue=default_user)
                        if username:
                            password = simpledialog.askstring("Windows Password", f"Enter password for {username}:", show='*')
                            if password:
                                run_args = ['/RU', username, '/RP', password]
            except Exception as cfg_err:
                logger.debug(f"Config check for UNC root skipped: {cfg_err}")
            
            logger.info(f"Creating scheduled task")
            logger.info(f"Action: {tr_action}")
            
            create_cmd = [
                'schtasks',
                '/Create',
                '/TN', 'AlliedTelesisBackup',
                '/TR', tr_action,
                '/SC', 'ONSTART',
                '/DELAY', '0000:30',  # 30 seconds delay after boot
                '/RL', 'HIGHEST',  # Highest privileges
                *run_args,
                '/F'  # Force create/overwrite
            ]
            
            result = subprocess.run(
                create_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                # Creation failed
                error_msg = result.stdout + result.stderr
                logger.error(f"Task creation failed: {error_msg}")
                
                # Check if it's permission error
                if "access is denied" in error_msg.lower() or "error" in error_msg.lower():
                    Messagebox.show_error(
                        "Setup failed - Administrator privileges required!\n\n"
                        "Please:\n"
                        "1. Close this application\n"
                        "2. Right-click the executable\n"
                        "3. Select 'Run as Administrator'\n"
                        "4. Try Setup Auto-Start again\n\n"
                        f"Technical error: {error_msg}",
                        "Admin Required"
                    )
                else:
                    Messagebox.show_error(
                        f"Failed to create scheduled task:\n\n{error_msg}\n\n"
                        "Possible solutions:\n"
                        "1. Run application as Administrator\n"
                        "2. Delete existing task if any (Task Scheduler)\n"
                        "3. Check Task Scheduler service is running",
                        "Setup Failed"
                    )
                
                if passphrase_file.exists():
                    passphrase_file.unlink()
                return
            
            logger.info("Task created successfully with SYSTEM account")
            
            # Auto-start the service immediately
            logger.info("Starting service now...")
            start_result = subprocess.run(
                ['schtasks', '/Run', '/TN', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            start_status = "\u2705 Service started!" if start_result.returncode == 0 else "\u26a0\ufe0f Starting... (check status in a moment)"
            
            Messagebox.show_info(
                "Auto-Start configured successfully!\n\n"
                "\u2705 Task created: AlliedTelesisBackup\n"
                "\u2705 Running as: SYSTEM account\n"
                "\u2705 Auto-start at Windows boot (30s delay)\n"
                f"{start_status}\n\n"
                "The service is now running 24/7 in background.\n\n"
                "Key Features:\n"
                "\u2022 Runs independently from GUI (can close anytime)\n"
                "\u2022 Reads schedules from database\n"
                "\u2022 Updates backup status to database\n"
                "\u2022 All changes in Schedules tab will sync automatically\n\n"
                "Check logs folder for service activity.",
                "Setup Complete"
            )
            logger.info("Task Scheduler auto-start configured with SYSTEM account and started")
            self._check_task_status()
                
        except Exception as e:
            Messagebox.show_error(f"Setup error: {str(e)}", "Error")
            logger.exception("Task Scheduler setup failed")
    
    def _start_task_service(self):
        """Start the service now using the scheduled task"""
        import subprocess
        
        try:
            # Check if task exists
            check_result = subprocess.run(
                ['schtasks', '/Query', '/TN', 'AlliedTelesisBackup'],
                capture_output=True,
                timeout=5
            )
            
            if check_result.returncode != 0:
                Messagebox.show_warning(
                    "Auto-start is not configured yet.\n\n"
                    "Please click 'Setup Auto-Start' first.",
                    "Not Setup"
                )
                return
            
            # Run the task now
            result = subprocess.run(
                ['schtasks', '/Run', '/TN', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                Messagebox.show_info(
                    "Service started successfully!\n\n"
                    "The backup service is now running in the background.\n"
                    "Check logs folder for activity.",
                    "Success"
                )
                logger.info("Backup service started via Task Scheduler")
                self._check_task_status()
            else:
                error_msg = result.stdout + result.stderr
                Messagebox.show_error(
                    f"Failed to start service:\n{error_msg}",
                    "Error"
                )
                logger.error(f"Failed to start task: {error_msg}")
                
        except Exception as e:
            Messagebox.show_error(f"Error starting service: {str(e)}", "Error")
            logger.exception("Task start failed")
    
    def _remove_autostart(self):
        """Remove auto-start configuration"""
        import subprocess
        from pathlib import Path
        
        # Check if task exists
        result = subprocess.run(
            ['schtasks', '/Query', '/TN', 'AlliedTelesisBackup'],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode != 0:
            Messagebox.show_info("Auto-start is not configured.", "Not Setup")
            return
        
        # Confirm removal
        if not Messagebox.show_question(
            "Remove auto-start configuration?\n\n"
            "This will:\n"
            "• Delete the scheduled task\n"
            "• Optionally delete stored passphrase\n\n"
            "Are you sure?",
            "Confirm Removal"
        ):
            return
        
        try:
            # Delete the task
            result = subprocess.run(
                ['schtasks', '/Delete', '/TN', 'AlliedTelesisBackup', '/F'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Ask about passphrase file
                delete_passphrase = Messagebox.show_question(
                    "Auto-start removed successfully!\n\n"
                    "Delete the stored passphrase file?\n"
                    "(You will need to re-enter it if you setup again)",
                    "Delete Passphrase?"
                )
                
                if delete_passphrase:
                    base_dir = get_base_dir()
                    passphrase_file = base_dir / "data" / ".service_passphrase"
                    if passphrase_file.exists():
                        passphrase_file.unlink()
                        logger.info("Service passphrase file deleted")
                
                Messagebox.show_info(
                    "Auto-start removed successfully!",
                    "Removal Complete"
                )
                logger.info("Task Scheduler auto-start removed")
                self._check_task_status()
            else:
                error_msg = result.stdout + result.stderr
                Messagebox.show_error(
                    f"Failed to remove task:\n{error_msg}",
                    "Error"
                )
                logger.error(f"Task removal failed: {error_msg}")
                
        except Exception as e:
            Messagebox.show_error(f"Removal error: {str(e)}", "Error")
            logger.exception("Task removal failed")
    
    def _show_task_instructions(self):
        """Show detailed setup instructions"""
        from tkinter import Toplevel
        import tkinter as tk
        
        instruction_window = Toplevel(self.parent)
        instruction_window.title("Auto-Start Setup Instructions")
        instruction_window.geometry("750x600")
        instruction_window.grab_set()
        
        frame = ttk.Frame(instruction_window, padding=20)
        frame.pack(fill=BOTH, expand=True)
        
        ttk.Label(
            frame,
            text="📖 Auto-Start Setup Guide",
            font=("-size", 14, "-weight", "bold")
        ).pack(pady=(0, 10))
        
        # Get current executable and working directory
        exe_path = sys.executable
        work_dir = str(Path.cwd())
        
        instructions = f"""
AUTOMATIC SETUP (Recommended):

1. Click "Setup Auto-Start" button
2. Enter your master passphrase
3. Service will start AUTOMATICALLY after setup!
4. Done! Service runs 24/7 and auto-starts on boot

═══════════════════════════════════════════════════

WHAT IT DOES:

• Creates Windows Scheduled Task named "AlliedTelesisBackup"
• Starts IMMEDIATELY after setup (no need to reboot)
• Auto-starts at Windows boot (30 second delay)
• Runs: {exe_path} --service
• Works: {work_dir}
• Runs in background (no window)
• UNLIMITED auto-restarts if fails (1 minute interval)
• Runs 24/7 independently of GUI

═══════════════════════════════════════════════════

HOW IT WORKS:

✅ Service runs in background continuously
✅ You can CLOSE the GUI - schedules keep running!
✅ Open GUI anytime to monitor/manage
✅ Service heartbeat every 30 minutes (see logs)
✅ Auto-recovery if service crashes

═══════════════════════════════════════════════════

MANUAL VERIFICATION:

1. Press Win+R
2. Type: taskschd.msc
3. Find: "AlliedTelesisBackup"
4. Status should show "Running"
5. Check logs folder for heartbeat messages

═══════════════════════════════════════════════════

ADVANTAGES:

✅ No Error 1053 issues
✅ More reliable than Windows Service
✅ Easy to setup and remove
✅ Unlimited auto-restart on failure
✅ Standard Windows feature
✅ No special tools needed
✅ GUI and Service run independently

═══════════════════════════════════════════════════

TROUBLESHOOTING:

If setup fails:
• Run application as Administrator
• Check passphrase is correct (min 8 chars)
• Check data folder exists
• See logs/app.log for details

If service won't start:
• Check passphrase file: data\\.service_passphrase
• Check task in Task Scheduler
• Check logs for errors
• Try Remove and Setup again

If schedules not running after GUI closed:
• Check Task Scheduler - task should show "Running"
• Check logs folder for heartbeat messages
• Service logs every 30 minutes when healthy
• Manual backup from GUI still works anytime

═══════════════════════════════════════════════════

IMPORTANT NOTES:

📌 Service starts automatically after setup
📌 Close GUI anytime - schedules keep running
📌 Service runs 24/7 until you remove it
📌 Check logs/app.log for service activity
        """
        
        text_widget = tk.Text(frame, wrap="word", height=25, width=80)
        text_widget.insert("1.0", instructions)
        text_widget.config(state="disabled")
        text_widget.pack(fill=BOTH, expand=True, pady=10)
        
        ttk.Button(
            frame,
            text="OK",
            command=instruction_window.destroy,
            bootstyle=PRIMARY
        ).pack()
    
    def _show_manual_setup_instructions(self, exe_path, working_dir):
        """Show manual setup instructions for Task Scheduler"""
        from tkinter import Toplevel, Text, Scrollbar
        import tkinter as tk
        
        instruction_window = Toplevel(self.parent)
        instruction_window.title("Manual Task Scheduler Setup")
        instruction_window.geometry("800x600")
        instruction_window.grab_set()
        
        frame = ttk.Frame(instruction_window, padding=20)
        frame.pack(fill=BOTH, expand=YES)
        
        ttk.Label(
            frame,
            text="📋 MANUAL SETUP INSTRUCTIONS",
            font=("-size", 14, "-weight", "bold")
        ).pack(pady=(0, 10))
        
        # Create scrolled text widget
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill=BOTH, expand=YES)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        text_widget = Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, font=("Consolas", 9))
        text_widget.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.config(command=text_widget.yview)
        
        instructions = f'''AUTOMATIC SETUP FAILED - FOLLOW THESE STEPS TO SETUP MANUALLY:

═══════════════════════════════════════════════════════════════
STEP 1: OPEN TASK SCHEDULER
═══════════════════════════════════════════════════════════════

1. Press Win+R on your keyboard
2. Type: taskschd.msc
3. Press Enter
4. Task Scheduler window will open

═══════════════════════════════════════════════════════════════
STEP 2: CREATE NEW TASK
═══════════════════════════════════════════════════════════════

1. In Task Scheduler, click "Create Task..." (right panel)
   (NOT "Create Basic Task")
2. A "Create Task" window will open

═══════════════════════════════════════════════════════════════
STEP 3: GENERAL TAB
═══════════════════════════════════════════════════════════════

Name: AlliedTelesisBackup
Description: Allied Telesis Backup Manager Background Service

Security options:
☑ Run whether user is logged on or not
☐ Do not store password
☑ Run with highest privileges

═══════════════════════════════════════════════════════════════
STEP 4: TRIGGERS TAB
═══════════════════════════════════════════════════════════════

1. Click "New..." button
2. Begin the task: "At log on"
3. Settings: "Specific user" (your username should be selected)
4. Click OK

═══════════════════════════════════════════════════════════════
STEP 5: ACTIONS TAB
═══════════════════════════════════════════════════════════════

1. Click "New..." button
2. Action: "Start a program"
3. Program/script: 
   {exe_path}

4. Add arguments: 
   --service

5. Start in:
   {working_dir}

6. Click OK

═══════════════════════════════════════════════════════════════
STEP 6: CONDITIONS TAB
═══════════════════════════════════════════════════════════════

Power:
☐ Start the task only if the computer is on AC power
☐ Stop if the computer switches to battery power

═══════════════════════════════════════════════════════════════
STEP 7: SETTINGS TAB
═══════════════════════════════════════════════════════════════

☑ Allow task to be run on demand
☑ Run task as soon as possible after a scheduled start is missed
☐ If the task fails, restart every: (leave unchecked)
☐ Stop the task if it runs longer than: (leave unchecked)

═══════════════════════════════════════════════════════════════
STEP 8: SAVE AND START
═══════════════════════════════════════════════════════════════

1. Click OK to save the task
2. You may be prompted for your password - enter it
3. Right-click the "AlliedTelesisBackup" task
4. Click "Run"
5. Task should start immediately

═══════════════════════════════════════════════════════════════
STEP 9: VERIFY IN APPLICATION
═══════════════════════════════════════════════════════════════

1. Go back to the application
2. Settings tab
3. Click "Refresh Status"
4. Task Status should show: "✅ Configured"
5. Service Status should show: "✅ Running"

═══════════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════════

If task still doesn't work:
• Make sure the paths above are correct
• Check that --service argument is exactly as shown
• Try running the task manually in Task Scheduler
• Check logs folder for errors
• Restart Windows and try again

═══════════════════════════════════════════════════════════════

COPY THESE VALUES (for easy paste):

Program/script:
{exe_path}

Add arguments:
--service

Start in:
{working_dir}

═══════════════════════════════════════════════════════════════
'''
        
        text_widget.insert('1.0', instructions)
        text_widget.config(state='disabled')
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        
        ttk.Button(
            button_frame,
            text="Open Task Scheduler",
            command=lambda: subprocess.Popen('taskschd.msc', shell=True),
            bootstyle=PRIMARY
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Close",
            command=instruction_window.destroy,
            bootstyle=SECONDARY
        ).pack(side=LEFT, padx=5)
    
    def _open_task_scheduler(self):
        """Open Windows Task Scheduler"""
        import subprocess
        import os
        
        try:
            # Use shell=True for Windows compatibility
            if os.name == 'nt':  # Windows
                subprocess.Popen('taskschd.msc', shell=True)
            else:
                subprocess.Popen(['taskschd.msc'])
            
            Messagebox.show_info(
                "Task Scheduler opened.\n\n"
                "Look for: AlliedTelesisBackup\n\n"
                "You can Start/Stop/Delete the task from there.",
                "Task Scheduler"
            )
        except Exception as e:
            logger.error(f"Failed to open Task Scheduler: {e}")
            Messagebox.show_error(
                f"Failed to open Task Scheduler.\n\n"
                f"Error: {e}\n\n"
                "You can open it manually:\n"
                "1. Press Win+R\n"
                "2. Type: taskschd.msc\n"
                "3. Press Enter",
                "Error"
            )
    
    def _check_service_status(self):
        """Check Windows service status"""
        import subprocess
        
        try:
            result = subprocess.run(
                ['sc', 'query', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                if 'running' in output:
                    self.service_status_var.set("✅ Running")
                    self.service_status_label.config(bootstyle="success")
                elif 'stopped' in output:
                    self.service_status_var.set("⏸️ Stopped")
                    self.service_status_label.config(bootstyle="warning")
                elif 'paused' in output:
                    self.service_status_var.set("⏸️ Paused")
                    self.service_status_label.config(bootstyle="warning")
                else:
                    self.service_status_var.set("❓ Unknown")
                    self.service_status_label.config(bootstyle="secondary")
            else:
                # Service not installed - show helpful message
                self.service_status_var.set("❌ Not Installed")
                self.service_status_label.config(bootstyle="secondary")
                logger.info("Windows Service not installed - use Task Scheduler instead")
                
        except Exception as e:
            # Error checking service - likely not installed
            self.service_status_var.set("❌ Not Installed")
            self.service_status_label.config(bootstyle="secondary")
            logger.debug(f"Service status check: {e}")
    
    def _start_service(self):
        """Start Windows service"""
        import subprocess
        
        try:
            result = subprocess.run(
                ['sc', 'start', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 or 'already been started' in result.stdout.lower():
                Messagebox.show_info("Service started successfully", "Success")
                logger.info("Windows service started")
                self._check_service_status()
            else:
                error_msg = result.stdout + result.stderr
                if 'access is denied' in error_msg.lower():
                    Messagebox.show_error(
                        "Access denied. Please run the application as Administrator to control the service.",
                        "Permission Error"
                    )
                else:
                    Messagebox.show_error(f"Failed to start service:\n{error_msg}", "Error")
                logger.error(f"Failed to start service: {error_msg}")
                
        except Exception as e:
            Messagebox.show_error(f"Error starting service: {str(e)}", "Error")
            logger.exception("Service start failed")
    
    def _stop_service(self):
        """Stop Windows service"""
        import subprocess
        
        if not Messagebox.show_question(
            "Stop the Windows service?\n\nScheduled backups will not run while the service is stopped.",
            "Confirm Stop"
        ):
            return
        
        try:
            result = subprocess.run(
                ['sc', 'stop', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 or 'has not been started' in result.stdout.lower():
                Messagebox.show_info("Service stopped successfully", "Success")
                logger.info("Windows service stopped")
                self._check_service_status()
            else:
                error_msg = result.stdout + result.stderr
                if 'access is denied' in error_msg.lower():
                    Messagebox.show_error(
                        "Access denied. Please run the application as Administrator to control the service.",
                        "Permission Error"
                    )
                else:
                    Messagebox.show_error(f"Failed to stop service:\n{error_msg}", "Error")
                logger.error(f"Failed to stop service: {error_msg}")
                
        except Exception as e:
            Messagebox.show_error(f"Error stopping service: {str(e)}", "Error")
            logger.exception("Service stop failed")
    
    def _restart_service(self):
        """Restart Windows service"""
        import subprocess
        
        if not Messagebox.show_question(
            "Restart the Windows service?\n\nThis will temporarily interrupt scheduled backups.",
            "Confirm Restart"
        ):
            return
        
        try:
            # Stop service
            subprocess.run(
                ['sc', 'stop', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Wait a moment
            import time
            time.sleep(2)
            
            # Start service
            result = subprocess.run(
                ['sc', 'start', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                Messagebox.show_info("Service restarted successfully", "Success")
                logger.info("Windows service restarted")
                self._check_service_status()
            else:
                error_msg = result.stdout + result.stderr
                if 'access is denied' in error_msg.lower():
                    Messagebox.show_error(
                        "Access denied. Please run the application as Administrator to control the service.",
                        "Permission Error"
                    )
                else:
                    Messagebox.show_error(f"Failed to restart service:\n{error_msg}", "Error")
                logger.error(f"Failed to restart service: {error_msg}")
                
        except Exception as e:
            Messagebox.show_error(f"Error restarting service: {str(e)}", "Error")
            logger.exception("Service restart failed")
    
    def _install_service(self):
        """Install Windows service"""
        import subprocess
        from pathlib import Path
        from tkinter import simpledialog
        
        # Check if pywin32 is properly installed
        try:
            import win32serviceutil
        except ImportError:
            if not Messagebox.show_question(
                "PyWin32 module not found or not properly installed.\n\n"
                "Would you like to install it now?\n\n"
                "This will run: pip install pywin32",
                "Install PyWin32?"
            ):
                return
            
            try:
                # Install pywin32
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', 'pywin32'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    Messagebox.show_error(
                        f"Failed to install pywin32:\n\n{result.stderr}",
                        "Installation Failed"
                    )
                    return
                
                # Run post-install script
                scripts_dir = Path(sys.executable).parent / "Scripts"
                postinstall_script = scripts_dir / "pywin32_postinstall.py"
                
                if postinstall_script.exists():
                    subprocess.run(
                        [sys.executable, str(postinstall_script), '-install'],
                        capture_output=True,
                        timeout=30
                    )
                
                Messagebox.show_info(
                    "PyWin32 installed successfully!\n\n"
                    "Please restart the application and try again.",
                    "Installation Complete"
                )
                return
                
            except Exception as e:
                Messagebox.show_error(
                    f"Failed to install pywin32: {str(e)}\n\n"
                    "Please install manually:\n"
                    "pip install pywin32",
                    "Error"
                )
                return
        
        # Check if service already installed
        try:
            result = subprocess.run(
                ['sc', 'query', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                Messagebox.show_warning(
                    "Service is already installed.\n\nUse Start/Stop buttons to control it, or Uninstall first to reinstall.",
                    "Already Installed"
                )
                return
        except:
            pass
        
        # Confirm installation
        if not Messagebox.show_question(
            "Install Allied Telesis Backup as Windows Service?\n\n"
            "This will:\n"
            "• Install the service for automatic startup\n"
            "• Configure it to start with Windows\n"
            "• Require administrator privileges\n\n"
            "You will need to provide the master passphrase.",
            "Confirm Installation"
        ):
            return
        
        # Get master passphrase
        passphrase = simpledialog.askstring(
            "Master Passphrase",
            "Enter the master passphrase for credential encryption:\n(Used to decrypt switch credentials)",
            show='*'
        )
        
        if not passphrase:
            Messagebox.show_warning("Installation cancelled - passphrase required", "Cancelled")
            return
        
        if len(passphrase) < 8:
            Messagebox.show_error(
                "Passphrase must be at least 8 characters long",
                "Invalid Passphrase"
            )
            return
        
        try:
            # Create data directory if needed
            base_dir = get_base_dir()
            data_dir = base_dir / "data"
            data_dir.mkdir(exist_ok=True)
            
            # Save passphrase to file
            passphrase_file = data_dir / ".service_passphrase"
            with open(passphrase_file, 'w', encoding='utf-8') as f:
                f.write(passphrase)
            
            # Persist base_dir override for Windows Service via ProgramData
            try:
                program_data = os.environ.get('PROGRAMDATA') or r"C:\\ProgramData"
                atbm_dir = Path(program_data) / "ATBM"
                atbm_dir.mkdir(parents=True, exist_ok=True)
                override_file = atbm_dir / "base_dir.txt"
                # Use exe directory when frozen, otherwise current base_dir
                if getattr(sys, 'frozen', False):
                    exe_dir = Path(sys.executable).parent
                    override_path = exe_dir
                else:
                    override_path = base_dir
                override_file.write_text(str(override_path), encoding='utf-8')
                logger.info(f"Wrote base_dir override to {override_file}: {override_path}")
            except Exception as e:
                logger.warning(f"Failed to write ProgramData base_dir override: {e}")
            
            logger.info("Installing Windows service...")
            
            # Use Python Windows Service installation (works for both source and executable)
            exe_path = sys.executable if getattr(sys, 'frozen', False) else 'python'
            service_script = str((get_base_dir() / 'app' / 'windows_service.py').absolute())
            
            # Build installation command
            if getattr(sys, 'frozen', False):
                # For executable, install with --service flag
                result = subprocess.run(
                    [exe_path, service_script, 'install'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                # For source code, use Python
                result = subprocess.run(
                    ['python', service_script, 'install'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            
            if result.returncode == 0 or 'installed' in result.stdout.lower():
                # Set to automatic startup
                subprocess.run(
                    ['sc', 'config', 'AlliedTelesisBackup', 'start=', 'auto'],
                    capture_output=True,
                    timeout=10
                )
                
                # Try to start service immediately
                start_res = subprocess.run(
                    ['sc', 'start', 'AlliedTelesisBackup'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                started = (start_res.returncode == 0)
                details = (start_res.stdout + start_res.stderr)
                if started:
                    logger.info("Windows service installed and started successfully")
                    Messagebox.show_info(
                        "Service installed and started successfully!\n\n"
                        "It will run in background and start with Windows.",
                        "Installation Complete"
                    )
                else:
                    logger.warning(f"Service start returned code {start_res.returncode}: {details}")
                    Messagebox.show_info(
                        "Service installed successfully, but start request may take time or require checking Services.msc.\n\n"
                        "You can also use Task Scheduler auto-start as an alternative.",
                        "Installation Complete"
                    )
                self._check_service_status()
            else:
                error_msg = result.stdout + result.stderr
                Messagebox.show_error(
                    f"Service installation failed:\n\n{error_msg}\n\n"
                    f"See SERVICE_INSTALLATION_GUIDE.md for alternative methods.",
                    "Installation Failed"
                )
                logger.error(f"Service installation failed: {error_msg}")
                
                # Clean up passphrase file on failure
                if passphrase_file.exists():
                    passphrase_file.unlink()
                    
        except Exception as e:
            Messagebox.show_error(f"Installation error: {str(e)}", "Error")
            logger.exception("Service installation failed")
    
    def _uninstall_service(self):
        """Uninstall Windows service"""
        import subprocess
        from pathlib import Path
        
        # Check if service is installed
        try:
            result = subprocess.run(
                ['sc', 'query', 'AlliedTelesisBackup'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                Messagebox.show_info(
                    "Service is not installed.",
                    "Not Installed"
                )
                return
        except:
            Messagebox.show_info("Service is not installed.", "Not Installed")
            return
        
        # Confirm uninstallation
        if not Messagebox.show_question(
            "Uninstall Allied Telesis Backup Windows Service?\n\n"
            "This will:\n"
            "• Stop the service if running\n"
            "• Remove the service from Windows\n"
            "• Optionally delete the stored passphrase\n\n"
            "Are you sure?",
            "Confirm Uninstall"
        ):
            return
        
        try:
            logger.info("Uninstalling Windows service...")
            
            # Stop service first
            subprocess.run(
                ['sc', 'stop', 'AlliedTelesisBackup'],
                capture_output=True,
                timeout=10
            )
            
            # Wait a moment
            import time
            time.sleep(1)
            
            # Check if running as executable or source
            if getattr(sys, 'frozen', False):
                # Running as executable - use sc delete
                service_name = "AlliedTelesisBackup"
                result = subprocess.run(
                    ['sc', 'delete', service_name],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                # Running from source - use Python script
                result = subprocess.run(
                    ['python', str((get_base_dir() / 'app' / 'windows_service.py').absolute()), 'remove'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            
            if result.returncode == 0 or 'removed' in result.stdout.lower() or 'deleted' in result.stdout.lower():
                # Ask about passphrase file
                delete_passphrase = Messagebox.show_question(
                    "Service uninstalled successfully!\n\n"
                    "Delete the stored passphrase file?\n"
                    "(You will need to re-enter it if you reinstall)",
                    "Delete Passphrase?"
                )
                
                if delete_passphrase:
                    base_dir = get_base_dir()
                    passphrase_file = base_dir / "data" / ".service_passphrase"
                    if passphrase_file.exists():
                        passphrase_file.unlink()
                        logger.info("Passphrase file deleted")
                
                Messagebox.show_info(
                    "Service uninstalled successfully!\n\n"
                    "You can still use the GUI application for manual backups.",
                    "Uninstall Complete"
                )
                logger.info("Windows service uninstalled successfully")
                self._check_service_status()
            else:
                error_msg = result.stdout + result.stderr
                if 'access is denied' in error_msg.lower():
                    Messagebox.show_error(
                        "Access denied.\n\nPlease run this application as Administrator to uninstall the service.",
                        "Permission Error"
                    )
                else:
                    Messagebox.show_error(
                        f"Uninstall failed:\n\n{error_msg}",
                        "Uninstall Error"
                    )
                logger.error(f"Service uninstall failed: {error_msg}")
                
        except Exception as e:
            Messagebox.show_error(f"Uninstall error: {str(e)}", "Error")
            logger.exception("Service uninstall failed")
    def _check_autologin_status(self):
        """Check if auto-login is enabled"""
        base_dir = get_base_dir()
        passphrase_file = base_dir / "data" / ".gui_passphrase"
        if passphrase_file.exists():
            self.autologin_status_label.config(
                text="Status: ✅ Enabled (passphrase saved)",
                foreground="green"
            )
        else:
            self.autologin_status_label.config(
                text="Status: ❌ Disabled (manual login required)",
                foreground="red"
            )
    
    def _enable_autologin(self):
        """Enable auto-login by saving current passphrase"""
        # Import save function from main
        from app.main import save_passphrase
        
        # Ask for confirmation
        if not Messagebox.show_question(
            "Enable Auto-Login?\n\n"
            "This will save your master passphrase with encryption.\n\n"
            "Benefits:\n"
            "• No passphrase prompt on startup\n"
            "• Application starts immediately\n\n"
            "Risks:\n"
            "• Passphrase stored on disk (encrypted)\n"
            "• Less secure than manual entry\n"
            "• Anyone with computer access can open app\n\n"
            "Only enable on trusted computers!\n\n"
            "Continue?",
            "Enable Auto-Login"
        ):
            return
        
        # Verify passphrase first
        passphrase = simpledialog.askstring(
            "Verify Passphrase",
            "Enter your master passphrase to enable auto-login:",
            show='*'
        )
        
        if not passphrase:
            return
        
        # Verify it's correct
        try:
            test_crypto = CryptoService(passphrase)
            # If no error, passphrase is correct
            save_passphrase(passphrase)
            Messagebox.show_info(
                "Auto-Login Enabled!\n\n"
                "✅ Passphrase saved successfully\n"
                "✅ Next startup will skip passphrase prompt\n\n"
                "To disable: Use 'Disable Auto-Login' button",
                "Success"
            )
            self._check_autologin_status()
            logger.info("Auto-login enabled")
        except Exception as e:
            Messagebox.show_error(
                f"Invalid passphrase or error:\n{str(e)}\n\n"
                "Auto-login NOT enabled.",
                "Error"
            )
    
    def _disable_autologin(self):
        """Disable auto-login by removing saved passphrase"""
        base_dir = get_base_dir()
        passphrase_file = base_dir / "data" / ".gui_passphrase"
        
        if not passphrase_file.exists():
            Messagebox.show_info(
                "Auto-login is already disabled.\n"
                "No action needed.",
                "Info"
            )
            return
        
        # Confirm
        if Messagebox.show_question(
            "Disable Auto-Login?\n\n"
            "This will delete the saved passphrase.\n"
            "You will be prompted for passphrase on next startup.\n\n"
            "Continue?",
            "Disable Auto-Login"
        ):
            try:
                passphrase_file.unlink()
                Messagebox.show_info(
                    "Auto-Login Disabled!\n\n"
                    "✅ Saved passphrase deleted\n"
                    "✅ Manual login required on next startup\n\n"
                    "Your data and credentials remain encrypted.",
                    "Success"
                )
                self._check_autologin_status()
                logger.info("Auto-login disabled")
            except Exception as e:
                Messagebox.show_error(
                    f"Error disabling auto-login:\n{str(e)}",
                    "Error"
                )
