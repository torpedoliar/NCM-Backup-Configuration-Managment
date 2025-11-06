"""Inventory view for managing switches"""
import logging
import threading
import asyncio
import time
from tkinter import messagebox, END
from queue import Queue
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
 

from app.data.repository import Repository
from app.services.crypto_service import CryptoService
from app.services.backup_service import BackupService
from app.net.ssh_client import SSHClient
from app.net.telnet_client import TelnetClient

logger = logging.getLogger(__name__)


class InventoryView:
    """Switch inventory management view"""
    
    def __init__(self, parent, crypto_service: CryptoService):
        self.parent = parent
        self.crypto = crypto_service
        self.backup_service = BackupService(crypto_service)
        self.queue = Queue()
        self.active_backups = set()  # Track active backup threads
        
        self.frame = ttk.Frame(parent, padding=10)
        self._create_ui()
        self._load_data()
        
        # Start queue polling
        self.frame.after(100, self._check_queue)
        
        # Auto-refresh every 30 seconds to catch scheduled backups
        self._start_auto_refresh()
    
    def _create_ui(self):
        """Create UI components"""
        # Toolbar
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill=X, pady=(0, 10))
        
        ttk.Button(
            toolbar,
            text="➜ Add Switch",
            command=self._add_switch,
            bootstyle=SUCCESS
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="📋 Batch Import",
            command=self._batch_import,
            bootstyle=SUCCESS
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="✏️ Edit",
            command=self._edit_switch,
            bootstyle=PRIMARY
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="🗑️ Delete",
            command=self._delete_switch,
            bootstyle=DANGER
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="🔄 Refresh",
            command=self._load_data,
            bootstyle=SECONDARY
        ).pack(side=LEFT, padx=5)
        
        ttk.Separator(toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)
        
        ttk.Button(
            toolbar,
            text="📥 Get Data",
            command=self._get_data,
            bootstyle=INFO,
            width=15
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="🗑️ Clear Console",
            command=self._clear_console,
            bootstyle=SECONDARY,
            width=15
        ).pack(side=LEFT, padx=5)
        ttk.Separator(toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)
        ttk.Button(
            toolbar,
            text="🖧 SSH Console",
            command=self._open_ssh_console,
            bootstyle=INFO,
            width=15
        ).pack(side=LEFT, padx=5)
        ttk.Button(
            toolbar,
            text="☎ Telnet Console",
            command=self._open_telnet_console,
            bootstyle=INFO,
            width=15
        ).pack(side=LEFT, padx=5)
        
        # Main content area with PanedWindow for split view
        paned = ttk.PanedWindow(self.frame, orient=VERTICAL)
        paned.pack(fill=BOTH, expand=YES)
        
        # Top pane - Table
        table_frame = ttk.Frame(paned)
        paned.add(table_frame, weight=3)
        
        columns = ("ID", "Name", "IP", "Protocol", "Port", "Credential", "Last Backup", "Status")
        
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=15
        )
        
        # Column configuration
        self.tree.column("ID", width=50, anchor=CENTER)
        self.tree.column("Name", width=150)
        self.tree.column("IP", width=150)
        self.tree.column("Protocol", width=80, anchor=CENTER)
        self.tree.column("Port", width=60, anchor=CENTER)
        self.tree.column("Credential", width=120)
        self.tree.column("Last Backup", width=160)
        self.tree.column("Status", width=100, anchor=CENTER)
        
        # Setup sortable columns
        self.sort_column = None
        self.sort_reverse = False
        
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by_column(c))
        
        # Configure row colors optimized for dark themes - vibrant text, no backgrounds
        self.tree.tag_configure('success', foreground='#4ade80')  # Bright green
        self.tree.tag_configure('failed', foreground='#f87171')   # Bright red
        self.tree.tag_configure('never', foreground='#94a3b8')    # Light gray
        
        # Scrollbar for table
        scrollbar = ttk.Scrollbar(table_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Bottom pane - Split console (left: system/background tasks, right: backup console)
        console_container = ttk.Frame(paned)
        paned.add(console_container, weight=1)
        
        # Create horizontal paned window for left/right split
        console_paned = ttk.PanedWindow(console_container, orient=HORIZONTAL)
        console_paned.pack(fill=BOTH, expand=YES)
        
        # Left side - Debug Console Monitoring
        left_console_frame = ttk.LabelFrame(console_paned, text="🖥️ Debug Console Monitoring", padding=5)
        console_paned.add(left_console_frame, weight=1)
        
        self.background_console = ttk.Text(
            left_console_frame,
            height=8,
            wrap=NONE,
            font=("Consolas", 9),
            state="disabled"
        )
        
        left_scrollbar_y = ttk.Scrollbar(left_console_frame, orient=VERTICAL, command=self.background_console.yview)
        left_scrollbar_x = ttk.Scrollbar(left_console_frame, orient=HORIZONTAL, command=self.background_console.xview)
        
        self.background_console.configure(
            yscrollcommand=left_scrollbar_y.set,
            xscrollcommand=left_scrollbar_x.set
        )
        
        self.background_console.pack(side=LEFT, fill=BOTH, expand=YES)
        left_scrollbar_y.pack(side=RIGHT, fill=Y)
        left_scrollbar_x.pack(side=BOTTOM, fill=X)
        
        # Right side - Backup Console
        right_console_frame = ttk.LabelFrame(console_paned, text="📥 Backup Console", padding=5)
        console_paned.add(right_console_frame, weight=1)
        
        self.console = ttk.Text(
            right_console_frame,
            height=8,
            wrap=NONE,
            font=("Consolas", 9),
            state="disabled"
        )
        
        right_scrollbar_y = ttk.Scrollbar(right_console_frame, orient=VERTICAL, command=self.console.yview)
        right_scrollbar_x = ttk.Scrollbar(right_console_frame, orient=HORIZONTAL, command=self.console.xview)
        
        self.console.configure(
            yscrollcommand=right_scrollbar_y.set,
            xscrollcommand=right_scrollbar_x.set
        )
        
        self.console.pack(side=LEFT, fill=BOTH, expand=YES)
        right_scrollbar_y.pack(side=RIGHT, fill=Y)
        right_scrollbar_x.pack(side=BOTTOM, fill=X)
    
    def _write_console(self, message: str, tag: str = "info"):
        """Write message to backup console (right)"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.console.config(state="normal")
        self.console.insert(END, f"[{timestamp}] {message}\n")
        self.console.see(END)
        self.console.config(state="disabled")
    
    def _write_background_console(self, message: str):
        """Write message to background tasks/system console (left)"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.background_console.config(state="normal")
        self.background_console.insert(END, f"[{timestamp}] {message}\n")
        self.background_console.see(END)
        self.background_console.config(state="disabled")
    
    def _clear_console(self):
        """Clear both consoles"""
        self.console.config(state="normal")
        self.console.delete("1.0", END)
        self.console.config(state="disabled")
        
        self.background_console.config(state="normal")
        self.background_console.delete("1.0", END)
        self.background_console.config(state="disabled")
    
    def _load_data(self):
        """Load switches into table with latest backup timestamps"""
        # Store current selection
        selected_items = self.tree.selection()
        selected_id = None
        if selected_items:
            selected_id = self.tree.item(selected_items[0])['values'][0]
        
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Load from DB
        with Repository() as repo:
            switches = repo.list_switches()
            
            for switch in switches:
                # Get last backup (includes both manual and automatic)
                last_backup = repo.get_latest_backup(switch.id)
                last_time = last_backup.taken_at.strftime("%Y-%m-%d %H:%M:%S") if last_backup else "Never"
                status = "✓ OK" if last_backup and last_backup.success else "✗ Failed" if last_backup else "-"
                
                # Determine row color tag based on status
                tag = ''
                if last_backup and last_backup.success:
                    tag = 'success'
                elif last_backup and not last_backup.success:
                    tag = 'failed'
                else:
                    tag = 'never'
                
                item_id = self.tree.insert("", END, values=(
                    switch.id,
                    switch.name,
                    switch.ip,
                    switch.protocol.upper(),
                    switch.port,
                    switch.credential.name,
                    last_time,
                    status
                ), tags=(tag,))
                
                # Restore selection
                if selected_id and switch.id == selected_id:
                    self.tree.selection_set(item_id)
    
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
        
        # Sort items - handle numeric columns
        if col in ('ID', 'Port'):
            # Numeric sort
            items.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0, reverse=self.sort_reverse)
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
    
    def _start_auto_refresh(self):
        """Auto-refresh table every 30 seconds to show updated backup times"""
        self._auto_refresh()
    
    def _auto_refresh(self):
        """Periodic refresh to catch scheduled backup updates"""
        try:
            # Check for recent scheduled backups
            from datetime import datetime, timedelta
            with Repository() as repo:
                switches = repo.list_switches()
                recent_threshold = datetime.now() - timedelta(seconds=35)
                
                for switch in switches:
                    last_backup = repo.get_latest_backup(switch.id)
                    if last_backup and last_backup.taken_at >= recent_threshold:
                        # Recent backup detected - log to background console
                        status = "✓ SUCCESS" if last_backup.success else "✗ FAILED"
                        self._write_background_console(
                            f"Scheduled backup detected: {switch.name} - {status}"
                        )
            
            self._load_data()
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
        
        # Schedule next refresh in 30 seconds
        self.frame.after(30000, self._auto_refresh)
    
    def _add_switch(self):
        """Add new switch"""
        SwitchDialog(self.frame, self.crypto, callback=self._load_data)
    
    def _edit_switch(self):
        """Edit selected switch"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a switch to edit", "No Selection")
            return
        
        switch_id = self.tree.item(selected[0])['values'][0]
        SwitchDialog(self.frame, self.crypto, switch_id=switch_id, callback=self._load_data)
    
    def _delete_switch(self):
        """Delete selected switch"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a switch to delete", "No Selection")
            return
        
        switch_name = self.tree.item(selected[0])['values'][1]
        if not Messagebox.show_question(
            f"Delete switch '{switch_name}' and all its backups?",
            "Confirm Delete"
        ):
            return
        
        switch_id = self.tree.item(selected[0])['values'][0]
        
        try:
            with Repository() as repo:
                repo.delete_switch(switch_id)
            Messagebox.show_info("Switch deleted successfully", "Success")
            self._load_data()
        except Exception as e:
            Messagebox.show_error(f"Failed to delete switch: {e}", "Error")
    
    def _batch_import(self):
        """Batch import switches from CSV file"""
        from tkinter import filedialog
        import csv
        
        # Ask for CSV file
        filename = filedialog.askopenfilename(
            title="Select CSV File to Import Switches",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        # Show import instructions
        instructions = (
            "CSV Format Expected:\n\n"
            "name,ip,protocol,port,credential_name,notes\n\n"
            "Example:\n"
            "Switch01,192.168.1.1,ssh,22,admin_cred,Main switch\n"
            "Switch02,192.168.1.2,telnet,23,user_cred,Backup switch\n\n"
            "Note: credential_name must match an existing credential."
        )
        
        if not Messagebox.show_question(
            instructions + "\n\nContinue with import?",
            "CSV Import Format"
        ):
            return
        
        try:
            imported = 0
            skipped = 0
            errors = []
            
            with open(filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                with Repository() as repo:
                    # Get all credentials
                    credentials = {c.name: c.id for c in repo.list_credentials()}
                    
                    for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header
                        try:
                            # Validate required fields
                            name = row.get('name', '').strip()
                            ip = row.get('ip', '').strip()
                            protocol = row.get('protocol', 'ssh').strip().lower()
                            port = row.get('port', '22').strip()
                            credential_name = row.get('credential_name', '').strip()
                            notes = row.get('notes', '').strip()
                            
                            if not name:
                                errors.append(f"Row {row_num}: Missing switch name")
                                skipped += 1
                                continue
                            
                            if not ip:
                                errors.append(f"Row {row_num}: Missing IP address")
                                skipped += 1
                                continue
                            
                            if not credential_name:
                                errors.append(f"Row {row_num}: Missing credential name")
                                skipped += 1
                                continue
                            
                            # Validate credential exists
                            if credential_name not in credentials:
                                errors.append(f"Row {row_num}: Credential '{credential_name}' not found")
                                skipped += 1
                                continue
                            
                            # Validate protocol
                            if protocol not in ['ssh', 'telnet']:
                                errors.append(f"Row {row_num}: Invalid protocol '{protocol}', must be 'ssh' or 'telnet'")
                                skipped += 1
                                continue
                            
                            # Validate port
                            try:
                                port = int(port)
                                if not 1 <= port <= 65535:
                                    raise ValueError()
                            except ValueError:
                                errors.append(f"Row {row_num}: Invalid port '{port}', must be 1-65535")
                                skipped += 1
                                continue
                            
                            # Check if switch already exists
                            switches = repo.list_switches()
                            existing = next((s for s in switches if s.name == name or s.ip == ip), None)
                            if existing:
                                errors.append(f"Row {row_num}: Switch with name '{name}' or IP '{ip}' already exists")
                                skipped += 1
                                continue
                            
                            # Create switch
                            repo.create_switch(
                                name=name,
                                ip=ip,
                                protocol=protocol,
                                port=port,
                                credential_id=credentials[credential_name],
                                notes=notes
                            )
                            imported += 1
                            self._write_console(f"Imported: {name} ({ip})")
                            
                        except Exception as e:
                            errors.append(f"Row {row_num}: {str(e)}")
                            skipped += 1
            
            # Show results
            result_msg = f"Import completed!\n\nImported: {imported}\nSkipped: {skipped}"
            
            if errors:
                result_msg += "\n\nErrors:\n" + "\n".join(errors[:10])  # Show first 10 errors
                if len(errors) > 10:
                    result_msg += f"\n... and {len(errors) - 10} more errors"
            
            if imported > 0:
                Messagebox.show_info(result_msg, "Import Complete")
            else:
                Messagebox.show_warning(result_msg, "Import Complete")
            
            self._load_data()
            
        except Exception as e:
            Messagebox.show_error(f"Failed to import CSV: {str(e)}", "Import Error")
            logger.exception("CSV import failed")
    
    def _get_data(self):
        """Execute backup for selected switch - supports parallel execution"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a switch", "No Selection")
            return
        
        switch_id = self.tree.item(selected[0])['values'][0]
        switch_name = self.tree.item(selected[0])['values'][1]
        switch_ip = self.tree.item(selected[0])['values'][2]
        switch_protocol = self.tree.item(selected[0])['values'][3]
        switch_port = self.tree.item(selected[0])['values'][4]
        
        # Check if backup is already running for this switch
        if switch_id in self.active_backups:
            Messagebox.show_warning(
                f"Backup for '{switch_name}' is already in progress.\n"
                f"Please wait for it to complete.",
                "Backup In Progress"
            )
            return
        
        # Add to active backups
        self.active_backups.add(switch_id)
        
        # Run backup in background thread (allows parallel execution)
        def worker():
            try:
                self.queue.put(('console', f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
                self.queue.put(('console', f"[{len(self.active_backups)} active] Starting backup for: {switch_name}"))
                self.queue.put(('console', f"Target: {switch_protocol}://{switch_ip}:{switch_port}"))
                self.queue.put(('console', f"Connecting via {switch_protocol}..."))
                
                logger.info(f"[PARALLEL BACKUP] Starting backup for {switch_name} ({len(self.active_backups)} active)")
                result = self.backup_service.execute_backup(switch_id, backup_type='manual')
                
                if result['success']:
                    self.queue.put(('console', f"✓ Backup completed successfully for {switch_name}"))
                    self.queue.put(('console', f"  - Size: {result['size_kb']:.1f} KB"))
                    self.queue.put(('console', f"  - File: {result['file_path']}"))
                    self.queue.put(('success', switch_name, switch_id))
                else:
                    self.queue.put(('console', f"✗ Backup failed for {switch_name}: {result['message']}"))
                    self.queue.put(('error', switch_name, result['message'], switch_id))
            except Exception as e:
                self.queue.put(('console', f"✗ Error for {switch_name}: {str(e)}"))
                self.queue.put(('error', switch_name, str(e), switch_id))
            finally:
                # Remove from active backups
                self.queue.put(('cleanup', switch_id))
        
        thread = threading.Thread(target=worker, daemon=True, name=f"Backup-{switch_name}")
        thread.start()
        
        active_count = len(self.active_backups)
        self._write_console(f"[{active_count} active] Backup initiated for {switch_name}")
        logger.info(f"Backup thread started for {switch_name} - Total active: {active_count}")
    
    def _open_ssh_console(self):
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a switch", "No Selection")
            return
        switch_id = self.tree.item(selected[0])['values'][0]
        with Repository() as repo:
            sw = repo.get_switch(switch_id)
            if not sw or not sw.credential:
                Messagebox.show_error("Switch or credential not found", "Error")
                return
            host = sw.ip
            port = sw.port
            enc_blob = sw.credential.enc_blob
        try:
            creds = self.crypto.decrypt_credential(enc_blob)
        except Exception as e:
            Messagebox.show_error(f"Failed to decrypt credential: {e}", "Error")
            return
        LiveConsoleDialog(self.frame, protocol='ssh', host=host, port=port, username=creds.get('username',''), password=creds.get('password',''), enable_password=creds.get('enable_password',''))
    
    def _open_telnet_console(self):
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a switch", "No Selection")
            return
        switch_id = self.tree.item(selected[0])['values'][0]
        with Repository() as repo:
            sw = repo.get_switch(switch_id)
            if not sw or not sw.credential:
                Messagebox.show_error("Switch or credential not found", "Error")
                return
            host = sw.ip
            port = sw.port
            enc_blob = sw.credential.enc_blob
        try:
            creds = self.crypto.decrypt_credential(enc_blob)
        except Exception as e:
            Messagebox.show_error(f"Failed to decrypt credential: {e}", "Error")
            return
        LiveConsoleDialog(self.frame, protocol='telnet', host=host, port=port, username=creds.get('username',''), password=creds.get('password',''), enable_password=creds.get('enable_password',''))
    
    def _check_queue(self):
        """Check for background task results"""
        try:
            while not self.queue.empty():
                result = self.queue.get_nowait()
                
                if result[0] == 'console':
                    self._write_console(result[1])
                elif result[0] == 'success':
                    switch_name = result[1]
                    switch_id = result[2]
                    # Don't show popup for every backup - just log to console
                    logger.info(f"Backup completed for {switch_name}")
                    self._load_data()
                elif result[0] == 'error':
                    switch_name = result[1]
                    error_msg = result[2]
                    switch_id = result[3]
                    Messagebox.show_error(f"Backup failed for {switch_name}: {error_msg}", "Backup Error")
                    self._load_data()
                elif result[0] == 'cleanup':
                    switch_id = result[1]
                    if switch_id in self.active_backups:
                        self.active_backups.remove(switch_id)
                    logger.info(f"Active backups remaining: {len(self.active_backups)}")
        except:
            pass
        
        # Schedule next check
        self.frame.after(100, self._check_queue)


class SwitchDialog:
    """Dialog for adding/editing switches"""
    
    def __init__(self, parent, crypto_service, switch_id=None, callback=None):
        self.crypto = crypto_service
        self.switch_id = switch_id
        self.callback = callback
        
        self.dialog = ttk.Toplevel(parent)
        self.dialog.title("Edit Switch" if switch_id else "Add Switch")
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_ui()
        
        if switch_id:
            self._load_switch_data()
    
    def _create_ui(self):
        """Create dialog UI"""
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill=BOTH, expand=YES)
        
        # Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=W, pady=5)
        self.name_var = ttk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)
        
        # IP
        ttk.Label(frame, text="IP/FQDN:").grid(row=1, column=0, sticky=W, pady=5)
        self.ip_var = ttk.StringVar()
        ttk.Entry(frame, textvariable=self.ip_var, width=40).grid(row=1, column=1, pady=5)
        
        # Protocol
        ttk.Label(frame, text="Protocol:").grid(row=2, column=0, sticky=W, pady=5)
        self.protocol_var = ttk.StringVar(value="ssh")
        protocol_frame = ttk.Frame(frame)
        protocol_frame.grid(row=2, column=1, sticky=W, pady=5)
        ttk.Radiobutton(protocol_frame, text="SSH", variable=self.protocol_var, value="ssh").pack(side=LEFT, padx=5)
        ttk.Radiobutton(protocol_frame, text="Telnet", variable=self.protocol_var, value="telnet").pack(side=LEFT, padx=5)
        
        # Port
        ttk.Label(frame, text="Port:").grid(row=3, column=0, sticky=W, pady=5)
        self.port_var = ttk.IntVar(value=22)
        ttk.Entry(frame, textvariable=self.port_var, width=40).grid(row=3, column=1, pady=5)
        
        # Add trace to auto-update port when protocol changes
        def on_protocol_change(*args):
            protocol = self.protocol_var.get()
            if protocol == "ssh":
                self.port_var.set(22)
            elif protocol == "telnet":
                self.port_var.set(23)
        
        self.protocol_var.trace_add("write", on_protocol_change)
        
        # Credential
        ttk.Label(frame, text="Credential:").grid(row=4, column=0, sticky=W, pady=5)
        self.credential_var = ttk.StringVar()
        
        # Load credentials
        with Repository() as repo:
            credentials = repo.list_credentials()
            cred_names = [c.name for c in credentials]
        
        if cred_names:
            self.credential_combo = ttk.Combobox(frame, textvariable=self.credential_var, values=cred_names, width=37, state="readonly")
            self.credential_combo.grid(row=4, column=1, pady=5)
            if cred_names:
                self.credential_combo.current(0)
        else:
            ttk.Label(frame, text="No credentials available. Add one first.", bootstyle="danger").grid(row=4, column=1, pady=5)
        
        # Notes
        ttk.Label(frame, text="Notes:").grid(row=5, column=0, sticky=NW, pady=5)
        self.notes_text = ttk.Text(frame, width=40, height=5)
        self.notes_text.grid(row=5, column=1, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Save", command=self._save, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy, bootstyle=SECONDARY).pack(side=LEFT, padx=5)
    
    def _load_switch_data(self):
        """Load existing switch data"""
        with Repository() as repo:
            switch = repo.get_switch(self.switch_id)
            if switch:
                self.name_var.set(switch.name)
                self.ip_var.set(switch.ip)
                self.protocol_var.set(switch.protocol)
                self.port_var.set(switch.port)
                self.credential_var.set(switch.credential.name)
                if switch.notes:
                    self.notes_text.insert("1.0", switch.notes)
    
    def _save(self):
        """Save switch"""
        name = self.name_var.get().strip()
        ip = self.ip_var.get().strip()
        protocol = self.protocol_var.get()
        port = self.port_var.get()
        cred_name = self.credential_var.get()
        notes = self.notes_text.get("1.0", END).strip()
        
        # Validation
        if not name:
            Messagebox.show_error("Name is required", "Validation Error")
            return
        
        if not ip:
            Messagebox.show_error("IP/FQDN is required", "Validation Error")
            return
        
        if not 1 <= port <= 65535:
            Messagebox.show_error("Port must be between 1 and 65535", "Validation Error")
            return
        
        if not cred_name:
            Messagebox.show_error("Credential is required", "Validation Error")
            return
        
        try:
            with Repository() as repo:
                # Get credential ID
                credential = repo.get_credential_by_name(cred_name)
                if not credential:
                    Messagebox.show_error("Selected credential not found", "Error")
                    return
                
                if self.switch_id:
                    # Update
                    repo.update_switch(
                        self.switch_id,
                        name=name,
                        ip=ip,
                        protocol=protocol,
                        port=port,
                        credential_id=credential.id,
                        notes=notes
                    )
                else:
                    # Create
                    repo.create_switch(name, ip, protocol, port, credential.id, notes)
            
            Messagebox.show_info("Switch saved successfully", "Success")
            self.dialog.destroy()
            
            if self.callback:
                self.callback()
        
        except Exception as e:
            Messagebox.show_error(f"Failed to save switch: {e}", "Error")

class LiveConsoleDialog:
    def __init__(self, parent, protocol: str, host: str, port: int, username: str, password: str, enable_password: str = ""):
        self.protocol = protocol
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.dialog = ttk.Toplevel(parent)
        title_proto = protocol.upper()
        self.dialog.title(f"{title_proto} Console - {host}:{port}")
        self.dialog.geometry("900x600")
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=BOTH, expand=YES)
        self.text = ttk.Text(frame, wrap=NONE, font=("Consolas", 10))
        scrollbar_y = ttk.Scrollbar(frame, orient=VERTICAL, command=self.text.yview)
        scrollbar_y.pack(side=RIGHT, fill=Y)
        self.text.configure(yscrollcommand=scrollbar_y.set)
        scrollbar_x = ttk.Scrollbar(self.dialog, orient=HORIZONTAL, command=self.text.xview)
        scrollbar_x.pack(fill=X)
        self.text.configure(xscrollcommand=scrollbar_x.set)
        self.text.pack(side=LEFT, fill=BOTH, expand=YES)
        entry_frame = ttk.Frame(self.dialog)
        entry_frame.pack(fill=X)
        self.cmd_var = ttk.StringVar()
        self.entry = ttk.Entry(entry_frame, textvariable=self.cmd_var)
        self.entry.pack(side=LEFT, fill=X, expand=YES, padx=5, pady=5)
        ttk.Button(entry_frame, text="Send", command=self._send).pack(side=LEFT, padx=5)
        self._auto_more_var = ttk.BooleanVar(value=True)
        ttk.Checkbutton(entry_frame, text="Auto-continue More", variable=self._auto_more_var, command=self._toggle_auto_more).pack(side=LEFT, padx=6)
        self.entry.bind('<Return>', lambda e: self._send())
        self.entry.bind('<space>', self._on_space_key)
        self.text.bind('<MouseWheel>', self._on_mousewheel)
        self.text.bind('<Shift-MouseWheel>', self._on_shift_mousewheel)
        self.text.bind('<space>', self._on_space_key_text)
        self.text.config(state="disabled")
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)
        self._ssh = None
        self._telnet = None
        self._loop = None
        self._stop = False
        self._telnet_reader_task = None
        self._auto_more_enabled = True
        self._last_auto_more = 0.0
        threading.Thread(target=self._connect_worker, daemon=True).start()
    
    def _on_mousewheel(self, event):
        delta = int(-1 * (event.delta / 120))
        self.text.yview_scroll(delta, "units")
        return "break"

    def _on_shift_mousewheel(self, event):
        delta = int(-1 * (event.delta / 120))
        self.text.xview_scroll(delta, "units")
        return "break"
    
    def _append(self, s: str):
        self.dialog.after(0, lambda: self._append_direct(s))

    def _append_direct(self, s: str):
        self.text.config(state="normal")
        self.text.insert(END, s)
        self.text.see(END)
        self.text.config(state="disabled")
    
    def _connect_worker(self):
        try:
            if self.protocol == 'ssh':
                self._ssh = SSHClient(self.host, int(self.port), self.username, self.password, self.enable_password)
                self._ssh.connect()
                self._append(f"Connected to {self.host} via SSH\n")
                threading.Thread(target=self._ssh_reader_worker, daemon=True).start()
            else:
                self._telnet = TelnetClient(self.host, int(self.port), self.username, self.password, self.enable_password)
                def loop_thread():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    self._loop = loop
                    try:
                        loop.run_until_complete(self._telnet.connect())
                        self._append(f"Connected to {self.host} via Telnet\n")
                        self._telnet_reader_task = loop.create_task(self._telnet_reader())
                        loop.run_forever()
                    except Exception as e:
                        self._append(f"Connection failed: {e}\n")
                    finally:
                        try:
                            loop.stop()
                        except Exception:
                            pass
                        loop.close()
                threading.Thread(target=loop_thread, daemon=True).start()
        except Exception as e:
            self._append(f"Connection failed: {e}\n")
    
    def _send(self):
        cmd = self.cmd_var.get().strip()
        if not cmd:
            return
        self.cmd_var.set("")
        if self.protocol == 'ssh' and self._ssh:
            try:
                self._append(f"> {cmd}\n")
                self._ssh.shell.send(cmd + "\n")
            except Exception as e:
                self._append(f"Error: {e}\n")
        elif self.protocol == 'telnet' and self._telnet and self._loop:
            try:
                self._append(f"> {cmd}\n")
                fut = asyncio.run_coroutine_threadsafe(self._telnet_write(cmd + "\n"), self._loop)
                fut.result(timeout=10)
            except Exception as e:
                self._append(f"Error: {e}\n")
        else:
            self._append("Not connected\n")
    
    def _on_space_key(self, event):
        if self.cmd_var.get().strip() == "":
            self._send_space()
            return "break"
        return None
    
    def _send_space(self):
        if self.protocol == 'ssh' and self._ssh:
            try:
                if getattr(self._ssh, 'shell', None):
                    self._ssh.shell.send(" ")
            except Exception as e:
                self._append(f"Error: {e}\n")
        elif self.protocol == 'telnet' and self._telnet and self._loop:
            try:
                fut = asyncio.run_coroutine_threadsafe(self._telnet_write(" "), self._loop)
                fut.result(timeout=5)
            except Exception as e:
                self._append(f"Error: {e}\n")
    
    def _on_space_key_text(self, event):
        self._send_space()
        return "break"
    
    def _on_close(self):
        try:
            self._stop = True
            if self._ssh:
                self._ssh.disconnect()
            if self._telnet:
                if self._loop:
                    try:
                        if self._telnet_reader_task:
                            self._loop.call_soon_threadsafe(self._telnet_reader_task.cancel)
                    except Exception:
                        pass
                    try:
                        fut = asyncio.run_coroutine_threadsafe(self._telnet.disconnect(), self._loop)
                        fut.result(timeout=5)
                    except Exception:
                        pass
                    self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
        self.dialog.destroy()

    def _ssh_reader_worker(self):
        try:
            while not self._stop and self._ssh and getattr(self._ssh, 'shell', None):
                try:
                    if self._ssh.shell.recv_ready():
                        chunk = self._ssh.shell.recv(65535).decode('utf-8', errors='ignore')
                        if chunk:
                            self._append(chunk)
                            if self._auto_more_enabled and self._should_auto_more(chunk):
                                now = time.time()
                                if now - self._last_auto_more > 0.2:
                                    try:
                                        self._ssh.shell.send(" ")
                                        self._last_auto_more = now
                                    except Exception:
                                        pass
                except Exception:
                    break
                finally:
                    time.sleep(0.1)
        except Exception:
            pass

    async def _telnet_write(self, data: str):
        self._telnet.writer.write(data)
        await self._telnet.writer.drain()

    async def _telnet_reader(self):
        try:
            while not self._stop and self._telnet and self._telnet.reader:
                try:
                    chunk = await asyncio.wait_for(self._telnet.reader.read(1024), timeout=0.3)
                except asyncio.TimeoutError:
                    continue
                if chunk:
                    self._append(chunk)
                    if self._auto_more_enabled and self._should_auto_more(chunk):
                        now = time.time()
                        if now - self._last_auto_more > 0.2:
                            try:
                                await self._telnet_write(" ")
                                self._last_auto_more = now
                            except Exception:
                                pass
        except Exception:
            pass

    def _toggle_auto_more(self):
        try:
            self._auto_more_enabled = bool(self._auto_more_var.get())
        except Exception:
            self._auto_more_enabled = True

    def _should_auto_more(self, text: str) -> bool:
        last = text[-200:].lower()
        tokens = (
            "--more--",
            "more:",
            " more ",
            "skipping one line",
            "press space",
            "press any key",
        )
        return any(tok in last for tok in tokens)
