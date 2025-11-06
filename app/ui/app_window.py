"""Main application window"""
import logging
from datetime import datetime
import threading
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.services.crypto_service import CryptoService
from app.services.schedule_service import ScheduleService
from app.services.retention_service import RetentionService
from app.ui.dashboard_view import DashboardView
from app.ui.inventory_view import InventoryView
from app.ui.credentials_view import CredentialsView
from app.ui.history_view import HistoryView
from app.ui.diff_view import DiffView
from app.ui.schedules_view import SchedulesView
from app.ui.settings_view import SettingsView

logger = logging.getLogger(__name__)


class AppWindow:
    """Main application window with tabbed interface"""
    
    def __init__(self, crypto_service: CryptoService,
                 schedule_service: ScheduleService,
                 retention_service: RetentionService):
        self.crypto = crypto_service
        self.schedule_service = schedule_service
        self.retention_service = retention_service
        
        # Create main window
        self.root = ttk.Window(themename="darkly")
        self.root.title("Allied Telesis Backup Configuration Management")
        self.root.geometry("1400x900")
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_reqwidth() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_reqheight() // 2)
        self.root.geometry(f"+{x}+{y}")
        
        self._create_ui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_ui(self):
        """Create UI components"""
        try:
            # Main container
            main_frame = ttk.Frame(self.root, padding=10)
            main_frame.pack(fill=BOTH, expand=YES)
            
            # Top bar with logos and date/time
            top_bar = ttk.Frame(main_frame)
            top_bar.pack(fill=X, pady=(0, 5))
            
            # Left side - Logo and title
            left_section = ttk.Frame(top_bar)
            left_section.pack(side=LEFT, fill=X, expand=NO)
            
            # Try to load and display company logo
            self.company_logo_label = None
            try:
                import yaml
                from pathlib import Path
                from PIL import Image, ImageTk
                from app.config import get_config_path
                
                config_path = get_config_path()
                if Path(config_path).exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    company_logo_path = config.get('branding', {}).get('company_logo')
                    if company_logo_path and Path(company_logo_path).exists():
                        # Load and resize logo
                        img = Image.open(company_logo_path)
                        img.thumbnail((200, 60), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        
                        self.company_logo_label = ttk.Label(left_section, image=photo)
                        self.company_logo_label.image = photo  # Keep reference
                        self.company_logo_label.pack(side=LEFT, padx=5)
            except Exception as e:
                logger.warning(f"Could not load company logo: {e}")
            
            ttk.Label(
                left_section,
                text="Allied Telesis Backup Configuration Management",
                font=("Segoe UI", 12, "bold")
            ).pack(side=LEFT, padx=5)
            
            # Right side - Application logo and datetime
            right_section = ttk.Frame(top_bar)
            right_section.pack(side=RIGHT, fill=X, expand=NO)
            
            self.datetime_label = ttk.Label(
                right_section,
                text="",
                font=("Consolas", 10),
                bootstyle="info"
            )
            self.datetime_label.pack(side=RIGHT, padx=10)
            
            # Try to load and display application logo
            self.app_logo_label = None
            try:
                import yaml
                from pathlib import Path
                from PIL import Image, ImageTk
                from app.config import get_config_path
                
                config_path = get_config_path()
                if Path(config_path).exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    app_logo_path = config.get('branding', {}).get('application_logo')
                    if app_logo_path and Path(app_logo_path).exists():
                        # Load and resize logo
                        img = Image.open(app_logo_path)
                        img.thumbnail((200, 60), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        
                        self.app_logo_label = ttk.Label(right_section, image=photo)
                        self.app_logo_label.image = photo  # Keep reference
                        self.app_logo_label.pack(side=RIGHT, padx=5)
            except Exception as e:
                logger.warning(f"Could not load application logo: {e}")
            
            # Separator
            ttk.Separator(main_frame, orient=HORIZONTAL).pack(fill=X, pady=5)
            
            # Create notebook (tabs)
            self.notebook = ttk.Notebook(main_frame)
            self.notebook.pack(fill=BOTH, expand=YES, pady=(0, 5))
            
            # Global console for all background tasks
            console_frame = ttk.LabelFrame(main_frame, text="🖥️ System Console - Background Tasks", padding=5)
            console_frame.pack(fill=X, pady=(5, 0))
            
            self.global_console = ttk.Text(
                console_frame,
                height=10,
                wrap=NONE,
                font=("Consolas", 9),
                state="disabled"
            )
            
            console_scrollbar_y = ttk.Scrollbar(console_frame, orient=VERTICAL, command=self.global_console.yview)
            console_scrollbar_x = ttk.Scrollbar(console_frame, orient=HORIZONTAL, command=self.global_console.xview)
            
            self.global_console.configure(
                yscrollcommand=console_scrollbar_y.set,
                xscrollcommand=console_scrollbar_x.set
            )
            
            self.global_console.pack(side=LEFT, fill=BOTH, expand=YES)
            console_scrollbar_y.pack(side=RIGHT, fill=Y)
            console_scrollbar_x.pack(side=BOTTOM, fill=X)
            
            # Create views
            logger.info("Creating Dashboard view...")
            self.dashboard_view = DashboardView(self.notebook)
            logger.info("Creating Inventory view...")
            self.inventory_view = InventoryView(self.notebook, self.crypto)
            logger.info("Creating Credentials view...")
            self.credentials_view = CredentialsView(self.notebook, self.crypto)
            logger.info("Creating History view...")
            self.history_view = HistoryView(self.notebook, self.crypto)
            logger.info("Creating Diff view...")
            self.diff_view = DiffView(self.notebook, self.crypto)
            logger.info("Creating Schedules view...")
            self.schedules_view = SchedulesView(self.notebook, self.schedule_service)
            logger.info("Creating Settings view...")
            self.settings_view = SettingsView(self.notebook, self.retention_service, self.crypto)
        except Exception as e:
            logger.exception(f"Error creating UI: {e}")
            raise
        
        # Add tabs
        self.notebook.add(self.dashboard_view.frame, text="📊 Dashboard")
        self.notebook.add(self.inventory_view.frame, text="📋 Inventory")
        self.notebook.add(self.credentials_view.frame, text="🔐 Credentials")
        self.notebook.add(self.history_view.frame, text="📁 Backup History")
        self.notebook.add(self.diff_view.frame, text="🔄 Diff Viewer")
        self.notebook.add(self.schedules_view.frame, text="⏰ Schedules")
        self.notebook.add(self.settings_view.frame, text="⚙️ Settings")
        
        # Start datetime updater
        self._update_datetime()
        
        # Write startup message to console
        self.write_console("System started - Monitoring background tasks...")
    
    def write_console(self, message: str, level: str = "INFO"):
        """Write message to global console"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}\n"
        if threading.current_thread() is threading.main_thread():
            self._append_console_line(line)
        else:
            try:
                self.root.after(0, self._append_console_line, line)
            except Exception:
                logging.getLogger(__name__).debug("Console write skipped: UI not available")

    def _append_console_line(self, line: str):
        self.global_console.config(state="normal")
        self.global_console.insert(END, line)
        self.global_console.see(END)
        self.global_console.config(state="disabled")
    
    def _update_datetime(self):
        """Update date/time display every second"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.datetime_label.config(text=f"📅 {current_time}")
        # Schedule next update
        self.root.after(1000, self._update_datetime)
    
    def _on_close(self):
        """Handle window close"""
        logger.info("Application closing")
        self.root.destroy()
    
    def run(self):
        """Start the application"""
        logger.info("Starting UI main loop")
        self.root.mainloop()
