"""Backup history view"""
import logging
from tkinter import filedialog
from tkinter import END
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.data.repository import Repository
from app.services.crypto_service import CryptoService
from app.services.backup_service import BackupService
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)


class HistoryView:
    """Backup history view"""
    
    def __init__(self, parent, crypto_service: CryptoService):
        self.parent = parent
        self.crypto = crypto_service
        self.backup_service = BackupService(crypto_service)
        self.export_service = ExportService()
        
        self.frame = ttk.Frame(parent, padding=10)
        self._create_ui()
        self._load_switches()
        
        # Start auto-refresh every 30 seconds
        self._start_auto_refresh()
    
    def _create_ui(self):
        """Create UI components"""
        # Switch selector and filter
        select_frame = ttk.Frame(self.frame)
        select_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(select_frame, text="Switch:").pack(side=LEFT, padx=5)
        self.switch_var = ttk.StringVar()
        self.switch_combo = ttk.Combobox(
            select_frame,
            textvariable=self.switch_var,
            state="readonly",
            width=30
        )
        self.switch_combo.pack(side=LEFT, padx=5)
        self.switch_combo.bind('<<ComboboxSelected>>', lambda e: self._load_backups())
        
        ttk.Label(select_frame, text="Type:").pack(side=LEFT, padx=(20, 5))
        self.filter_var = ttk.StringVar(value="All")
        self.filter_combo = ttk.Combobox(
            select_frame,
            textvariable=self.filter_var,
            state="readonly",
            values=["All", "Manual", "Automatic"],
            width=15
        )
        self.filter_combo.pack(side=LEFT, padx=5)
        self.filter_combo.bind('<<ComboboxSelected>>', lambda e: self._load_backups())
        
        ttk.Label(select_frame, text="Month:").pack(side=LEFT, padx=(20, 5))
        self.month_filter_var = ttk.StringVar(value="All Months")
        self.month_filter_combo = ttk.Combobox(
            select_frame,
            textvariable=self.month_filter_var,
            state="readonly",
            width=18
        )
        self.month_filter_combo.pack(side=LEFT, padx=5)
        self.month_filter_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())
        
        ttk.Button(
            select_frame,
            text="🔄 Refresh",
            command=self._refresh_all,
            bootstyle=SECONDARY
        ).pack(side=LEFT, padx=5)
        
        # Search bar
        search_frame = ttk.Frame(self.frame)
        search_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(search_frame, text="🔍 Search:").pack(side=LEFT, padx=5)
        self.search_var = ttk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=40
        )
        self.search_entry.pack(side=LEFT, padx=5)
        self.search_var.trace('w', lambda *args: self._apply_filters())
        
        ttk.Label(
            search_frame,
            text="(Search by timestamp, hash, status, or message)",
            bootstyle="secondary",
            font=("", 8)
        ).pack(side=LEFT, padx=5)
        
        # Toolbar
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill=X, pady=(0, 10))
        
        ttk.Button(
            toolbar,
            text="👁️ View",
            command=self._view_backup,
            bootstyle=INFO
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="💾 Export",
            command=self._export_backup,
            bootstyle=SUCCESS
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="📁 Open Folder",
            command=self._open_folder,
            bootstyle=SECONDARY
        ).pack(side=LEFT, padx=5)
        
        # Table
        columns = ("ID", "Timestamp", "Size (KB)", "Hash", "Status", "Job/Schedule", "Message")
        
        self.tree = ttk.Treeview(
            self.frame,
            columns=columns,
            show="headings",
            height=20
        )
        
        self.tree.column("ID", width=50, anchor=CENTER)
        self.tree.column("Timestamp", width=160)
        self.tree.column("Size (KB)", width=100, anchor=CENTER)
        self.tree.column("Hash", width=150)
        self.tree.column("Status", width=100, anchor=CENTER)
        self.tree.column("Job/Schedule", width=120, anchor=CENTER)
        self.tree.column("Message", width=300)
        
        # Setup sortable columns
        self.sort_column = None
        self.sort_reverse = False
        
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by_column(c))
        
        # Configure row colors optimized for dark themes - no backgrounds, vibrant text
        self.tree.tag_configure('success_auto', foreground='#4ade80')
        self.tree.tag_configure('success_manual', foreground='#22d3ee')
        self.tree.tag_configure('failed_auto', foreground='#f87171')
        self.tree.tag_configure('failed_manual', foreground='#fb923c')
        self.tree.tag_configure('success', foreground='#4ade80')
        self.tree.tag_configure('failed', foreground='#f87171')
        self.tree.tag_configure('updated', foreground='#facc15')
        
        scrollbar = ttk.Scrollbar(self.frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)
    
    def _refresh_all(self):
        """Refresh switch list and backups"""
        current_selection = self.switch_var.get()
        self._load_switches()
        
        # Try to restore previous selection if it still exists
        if current_selection and current_selection in self.switch_combo['values']:
            self.switch_combo.set(current_selection)
        self._load_backups()
    
    def _load_switches(self):
        """Load switches into combo"""
        with Repository() as repo:
            switches = repo.list_switches()
            switch_names = [s.name for s in switches]
            self.switch_combo['values'] = switch_names
            if switch_names and not self.switch_var.get():
                self.switch_combo.current(0)
    
    def _load_backups(self):
        """Load backups for selected switch and populate month filter"""
        from datetime import timedelta
        
        switch_name = self.switch_var.get()
        if not switch_name:
            return
        
        filter_type = self.filter_var.get()
        
        with Repository() as repo:
            switch = repo.get_switch_by_name(switch_name)
            if not switch:
                return
            
            backups = repo.list_backups(switch_id=switch.id)
            
            # Store all backups data for filtering
            self.all_backups_data = []
            month_set = set()
            
            for backup in backups:
                # Determine if automatic backup
                backup_type = getattr(backup, 'backup_type', 'manual')
                is_automatic = (backup_type == 'automatic')
                
                # Get job/schedule info if automatic
                job_info = None
                if is_automatic and hasattr(backup, 'job_id') and backup.job_id:
                    job = repo.get_job(backup.job_id)
                    if job:
                        interval_map = {
                            15: '15 min',
                            60: '1 hour',
                            360: '6 hours',
                            720: '12 hours',
                            1440: 'Daily',
                            10080: 'Weekly',
                            43200: 'Monthly'
                        }
                        interval_str = interval_map.get(job.interval_minutes, f'{job.interval_minutes}m')
                        job_info = f"Job #{job.id} ({interval_str})"
                
                # Apply type filter
                if filter_type == "Manual" and is_automatic:
                    continue
                elif filter_type == "Automatic" and not is_automatic:
                    continue
                
                size_kb = backup.size_bytes / 1024 if backup.size_bytes else 0
                status = "✓ Success" if backup.success else "✗ Failed"
                hash_short = backup.content_hash[:16] if backup.content_hash else "-"
                
                # Add type indicator
                backup_type = "🤖 Auto" if is_automatic else "👤 Manual"
                message_with_type = f"{backup_type} | {backup.message or '-'}"
                
                # Store backup data
                backup_data = {
                    'id': backup.id,
                    'taken_at': backup.taken_at,
                    'timestamp_str': backup.taken_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'size_kb': size_kb,
                    'hash_short': hash_short,
                    'status': status,
                    'message': message_with_type,
                    'job_info': job_info or '-'
                }
                self.all_backups_data.append(backup_data)
                
                # Collect months for filter
                month_str = backup.taken_at.strftime('%Y-%m')
                month_set.add(month_str)
            
            # Update month filter dropdown
            month_list = sorted(list(month_set), reverse=True)
            month_labels = ["All Months"] + [f"{m} ({self._count_backups_for_month(m)})" for m in month_list]
            self.month_filter_combo['values'] = month_labels
            if self.month_filter_var.get() not in month_labels:
                self.month_filter_var.set("All Months")
            
            # Apply filters and display
            self._apply_filters()
    
    def _count_backups_for_month(self, month_str: str) -> int:
        """Count backups for a specific month"""
        count = 0
        for b in self.all_backups_data:
            if b['taken_at'].strftime('%Y-%m') == month_str:
                count += 1
        return count
    
    def _apply_filters(self):
        """Apply month and search filters to backup list"""
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not hasattr(self, 'all_backups_data'):
            return
        
        # Get filter values
        month_filter_text = self.month_filter_var.get()
        search_text = self.search_var.get().lower()
        
        # Extract month from filter text
        if month_filter_text == "All Months":
            month_filter = None
        else:
            month_filter = month_filter_text.split(' ')[0]
        
        # Filter backups
        filtered_backups = []
        for backup_data in self.all_backups_data:
            # Apply month filter
            if month_filter:
                if backup_data['taken_at'].strftime('%Y-%m') != month_filter:
                    continue
            
            # Apply search filter
            if search_text:
                searchable = (
                    backup_data['timestamp_str'] +
                    backup_data['hash_short'] +
                    backup_data['status'] +
                    backup_data['message']
                ).lower()
                
                if search_text not in searchable:
                    continue
            
            filtered_backups.append(backup_data)
        
        # Display filtered backups
        idx = 1
        for backup_data in filtered_backups:
            # Determine combined color tag based on status and type
            tag = str(backup_data['id'])
            
            is_success = '✓ Success' in backup_data['status']
            is_auto = '🤖 Auto' in backup_data['message']
            is_manual = '👤 Manual' in backup_data['message']
            
            # Use combined tags for better visual differentiation
            if is_success and is_auto:
                color_tag = 'success_auto'
            elif is_success and is_manual:
                color_tag = 'success_manual'
            elif not is_success and is_auto:
                color_tag = 'failed_auto'
            elif not is_success and is_manual:
                color_tag = 'failed_manual'
            elif is_success:
                color_tag = 'success'
            else:
                color_tag = 'failed'
            
            tags = (tag, color_tag)
            if 'Perubahan konfigurasi terdeteksi' in backup_data['message']:
                tags = (tag, 'updated')
            
            self.tree.insert("", END, values=(
                idx,
                backup_data['timestamp_str'],
                f"{backup_data['size_kb']:.2f}",
                backup_data['hash_short'],
                backup_data['status'],
                backup_data['job_info'],
                backup_data['message']
            ), tags=tags)
            idx += 1
    
    def _sort_by_column(self, col):
        """Sort treeview by column"""
        # Toggle sort direction if clicking same column
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_reverse = False
        self.sort_column = col
        
        # Get all items with their values
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]
        
        # Sort items - handle numeric and date columns
        if col == 'ID':
            # Numeric sort
            items.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0, reverse=self.sort_reverse)
        elif col == 'Size (KB)':
            # Numeric sort for size
            items.sort(key=lambda x: float(x[0]) if x[0].replace('.', '').isdigit() else 0, reverse=self.sort_reverse)
        elif col == 'Timestamp':
            # Date sort
            items.sort(key=lambda x: x[0], reverse=self.sort_reverse)
        else:
            # String sort
            items.sort(key=lambda x: x[0].lower(), reverse=self.sort_reverse)
        
        # Rearrange items in sorted positions
        for index, (val, item) in enumerate(items):
            self.tree.move(item, '', index)
        
        # Update column heading to show sort direction
        for column in self.tree['columns']:
            heading = column
            if column == col:
                heading = f"{column} {'▼' if self.sort_reverse else '▲'}"
            self.tree.heading(column, text=heading, command=lambda c=column: self._sort_by_column(c))
    
    def _view_backup(self):
        """View selected backup content"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a backup", "No Selection")
            return
        
        # Get actual backup ID from tags
        backup_id = int(self.tree.item(selected[0])['tags'][0])
        
        with Repository() as repo:
            backup = repo.get_backup(backup_id)
            if not backup or not backup.success:
                Messagebox.show_error("Backup file not available", "Error")
                return
            
            try:
                content = self.backup_service.get_backup_content(backup)
                ViewerDialog(self.frame, "Backup Configuration", content)
            except Exception as e:
                Messagebox.show_error(f"Failed to read backup: {e}", "Error")
    
    def _export_backup(self):
        """Export selected backup"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a backup", "No Selection")
            return
        
        backup_id = int(self.tree.item(selected[0])['tags'][0])
        
        dest_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if not dest_path:
            return
        
        with Repository() as repo:
            backup = repo.get_backup(backup_id)
            if not backup or not backup.success:
                Messagebox.show_error("Backup file not available", "Error")
                return
            
            try:
                if self.export_service.export_config(backup, dest_path):
                    Messagebox.show_info(f"Exported to {dest_path}", "Success")
            except Exception as e:
                Messagebox.show_error(f"Export failed: {e}", "Error")
    
    def _open_folder(self):
        """Open backup file's folder"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a backup", "No Selection")
            return
        
        backup_id = int(self.tree.item(selected[0])['tags'][0])
        
        with Repository() as repo:
            backup = repo.get_backup(backup_id)
            if not backup or not backup.file_path:
                Messagebox.show_error("Backup file not available", "Error")
                return
            
            self.export_service.open_containing_folder(backup.file_path)
    
    def _start_auto_refresh(self):
        """Start auto-refresh timer"""
        self._auto_refresh()
    
    def _auto_refresh(self):
        """Auto-refresh history view every 30 seconds"""
        try:
            # Store current switch selection
            current_switch = self.switch_var.get()
            if current_switch:
                # Silently reload backups without changing user's view
                self._load_backups()
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
        
        # Schedule next refresh in 30 seconds
        self.frame.after(30000, self._auto_refresh)


class ViewerDialog:
    """Dialog for viewing text content"""
    
    def __init__(self, parent, title, content):
        self.dialog = ttk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=BOTH, expand=YES)
        
        text_widget = ttk.Text(frame, wrap=NONE)
        text_widget.pack(side=LEFT, fill=BOTH, expand=YES)
        
        scrollbar_y = ttk.Scrollbar(frame, orient=VERTICAL, command=text_widget.yview)
        scrollbar_y.pack(side=RIGHT, fill=Y)
        text_widget.configure(yscrollcommand=scrollbar_y.set)
        
        scrollbar_x = ttk.Scrollbar(self.dialog, orient=HORIZONTAL, command=text_widget.xview)
        scrollbar_x.pack(fill=X)
        text_widget.configure(xscrollcommand=scrollbar_x.set)
        
        text_widget.insert("1.0", content)
        text_widget.configure(state="disabled")
        
        ttk.Button(
            self.dialog,
            text="Close",
            command=self.dialog.destroy,
            bootstyle=SECONDARY
        ).pack(pady=5)
