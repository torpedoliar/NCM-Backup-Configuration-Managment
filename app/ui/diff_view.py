"""Diff viewer for comparing configurations"""
import logging
import os
from tkinter import filedialog, END
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.data.repository import Repository
from app.services.crypto_service import CryptoService
from app.services.backup_service import BackupService
from app.services.diff_service import DiffService
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)


class DiffView:
    """Configuration diff viewer"""
    
    def __init__(self, parent, crypto_service: CryptoService):
        self.parent = parent
        self.crypto = crypto_service
        self.backup_service = BackupService(crypto_service)
        self.diff_service = DiffService()
        self.export_service = ExportService()
        
        self.frame = ttk.Frame(parent, padding=10)
        self.all_backups = []  # Store all backups for filtering
        self.manual_before_path = None  # Manual file path for Before
        self.manual_after_path = None  # Manual file path for After
        self._create_ui()
        self._load_switches()
    
    def _create_ui(self):
        """Create UI components"""
        # Selection frame
        select_frame = ttk.LabelFrame(self.frame, text="Select Backups", padding=10)
        select_frame.pack(fill=X, pady=(0, 10))
        
        # Switch
        row1 = ttk.Frame(select_frame)
        row1.pack(fill=X, pady=5)
        ttk.Label(row1, text="Switch:", width=12).pack(side=LEFT)
        self.switch_var = ttk.StringVar()
        self.switch_combo = ttk.Combobox(row1, textvariable=self.switch_var, state="readonly", width=30)
        self.switch_combo.pack(side=LEFT, padx=5)
        self.switch_combo.bind("<<ComboboxSelected>>", lambda e: self._load_backups())
        
        ttk.Button(
            row1,
            text="🔄 Refresh",
            command=self._refresh_all,
            bootstyle=SECONDARY,
            width=10
        ).pack(side=LEFT, padx=5)
        
        # Backup 1 (Before)
        row2 = ttk.Frame(select_frame)
        row2.pack(fill=X, pady=5)
        ttk.Label(row2, text="Before:", width=12).pack(side=LEFT)
        self.backup1_var = ttk.StringVar()
        self.backup1_combo = ttk.Combobox(row2, textvariable=self.backup1_var, state="readonly", width=30, height=20)
        self.backup1_combo.pack(side=LEFT, padx=5)
        
        # Before month filter
        self.before_month_var = ttk.StringVar(value="All")
        self.before_month_combo = ttk.Combobox(row2, textvariable=self.before_month_var, state="readonly", width=12)
        self.before_month_combo.pack(side=LEFT, padx=2)
        self.before_month_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_before_filter())
        
        # Browse button for Before
        ttk.Button(
            row2,
            text="📁 Browse",
            command=self._browse_before_file,
            bootstyle=SECONDARY,
            width=10
        ).pack(side=LEFT, padx=2)
        
        # Backup 2 (After)
        row3 = ttk.Frame(select_frame)
        row3.pack(fill=X, pady=5)
        ttk.Label(row3, text="After:", width=12).pack(side=LEFT)
        self.backup2_var = ttk.StringVar()
        self.backup2_combo = ttk.Combobox(row3, textvariable=self.backup2_var, state="readonly", width=30, height=20)
        self.backup2_combo.pack(side=LEFT, padx=5)
        
        # After month filter
        self.after_month_var = ttk.StringVar(value="All")
        self.after_month_combo = ttk.Combobox(row3, textvariable=self.after_month_var, state="readonly", width=12)
        self.after_month_combo.pack(side=LEFT, padx=2)
        self.after_month_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_after_filter())
        
        # Browse button for After
        ttk.Button(
            row3,
            text="📁 Browse",
            command=self._browse_after_file,
            bootstyle=SECONDARY,
            width=10
        ).pack(side=LEFT, padx=2)
        
        # Buttons
        btn_row = ttk.Frame(select_frame)
        btn_row.pack(fill=X, pady=5)
        
        ttk.Button(
            btn_row,
            text="⚡ Latest vs Previous",
            command=self._select_latest,
            bootstyle=INFO
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            btn_row,
            text="🔄 Show Diff",
            command=self._show_diff,
            bootstyle=SUCCESS
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            btn_row,
            text="💾 Export Diff",
            command=self._export_diff,
            bootstyle=SECONDARY
        ).pack(side=LEFT, padx=5)
        
        # Stats frame
        self.stats_frame = ttk.Frame(self.frame)
        self.stats_frame.pack(fill=X, pady=(0, 10))
        
        self.stats_label = ttk.Label(self.stats_frame, text="", bootstyle="info")
        self.stats_label.pack()
        
        # Side-by-side diff display
        diff_container = ttk.Frame(self.frame)
        diff_container.pack(fill=BOTH, expand=YES)
        
        # Left side - BEFORE
        left_frame = ttk.LabelFrame(diff_container, text="📄 BEFORE", padding=5)
        left_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 5))
        
        self.before_text = ttk.Text(left_frame, wrap=NONE, font=("Consolas", 9))
        before_scroll_y = ttk.Scrollbar(left_frame, orient=VERTICAL, command=self.before_text.yview)
        before_scroll_x = ttk.Scrollbar(left_frame, orient=HORIZONTAL, command=self.before_text.xview)
        
        self.before_text.configure(yscrollcommand=before_scroll_y.set, xscrollcommand=before_scroll_x.set)
        
        self.before_text.grid(row=0, column=0, sticky="nsew")
        before_scroll_y.grid(row=0, column=1, sticky="ns")
        before_scroll_x.grid(row=1, column=0, sticky="ew")
        
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        
        # Right side - AFTER
        right_frame = ttk.LabelFrame(diff_container, text="📄 AFTER", padding=5)
        right_frame.pack(side=RIGHT, fill=BOTH, expand=YES, padx=(5, 0))
        
        self.after_text = ttk.Text(right_frame, wrap=NONE, font=("Consolas", 9))
        after_scroll_y = ttk.Scrollbar(right_frame, orient=VERTICAL, command=self.after_text.yview)
        after_scroll_x = ttk.Scrollbar(right_frame, orient=HORIZONTAL, command=self.after_text.xview)
        
        self.after_text.configure(yscrollcommand=after_scroll_y.set, xscrollcommand=after_scroll_x.set)
        
        self.after_text.grid(row=0, column=0, sticky="nsew")
        after_scroll_y.grid(row=0, column=1, sticky="ns")
        after_scroll_x.grid(row=1, column=0, sticky="ew")
        
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Configure tags for highlighting differences
        self.before_text.tag_config("removed", background="#4d0000", foreground="#ff6b6b")
        self.before_text.tag_config("changed", background="#4d4d00", foreground="#ffeb3b")
        self.before_text.tag_config("same", foreground="#cccccc")
        
        self.after_text.tag_config("added", background="#004d00", foreground="#69f0ae")
        self.after_text.tag_config("changed", background="#4d4d00", foreground="#ffeb3b")
        self.after_text.tag_config("same", foreground="#cccccc")
        
        # Synchronize scrolling
        self.before_text.bind("<MouseWheel>", lambda e: self._sync_scroll(e))
        self.after_text.bind("<MouseWheel>", lambda e: self._sync_scroll(e))
        
        self.current_diff = ""
    
    def _refresh_all(self):
        """Refresh switch list and backups"""
        current_selection = self.switch_var.get()
        self._load_switches()
        
        # Try to restore previous selection if it still exists
        if current_selection and current_selection in self.switch_combo['values']:
            self.switch_combo.set(current_selection)
        self._load_backups()
    
    def _load_switches(self):
        """Load switches"""
        with Repository() as repo:
            switches = repo.list_switches()
            names = [s.name for s in switches]
            self.switch_combo['values'] = names
            if names and not self.switch_var.get():
                self.switch_combo.current(0)
    
    def _load_backups(self):
        """Load backups for selected switch"""
        switch_name = self.switch_var.get()
        if not switch_name:
            return
        
        with Repository() as repo:
            switch = repo.get_switch_by_name(switch_name)
            if not switch:
                return
            
            backups = repo.list_backups(switch_id=switch.id)
            # Convert to dict to avoid SQLAlchemy DetachedInstanceError
            self.all_backups = [
                {
                    'id': b.id,
                    'taken_at': b.taken_at,
                    'size_bytes': b.size_bytes,
                    'file_path': b.file_path
                }
                for b in backups if b.success
            ]
            
            # Build month filter list
            month_set = set()
            for b in self.all_backups:
                month_str = b['taken_at'].strftime('%Y-%m')
                month_set.add(month_str)
            
            month_list = sorted(list(month_set), reverse=True)
            month_labels = ["All"] + month_list
            
            # Update both before and after month filters
            self.before_month_combo['values'] = month_labels
            self.after_month_combo['values'] = month_labels
            self.before_month_var.set("All")
            self.after_month_var.set("All")
            
            # Display all backups initially
            self._apply_before_filter()
            self._apply_after_filter()
    
    def _count_backups_for_month(self, month_str: str) -> int:
        """Count backups for a specific month"""
        count = 0
        for b in self.all_backups:
            if b['taken_at'].strftime('%Y-%m') == month_str:
                count += 1
        return count
    
    def _apply_before_filter(self):
        """Apply month filter to Before backup list"""
        filter_text = self.before_month_var.get()
        
        if filter_text == "All":
            filtered_backups = self.all_backups
        else:
            filtered_backups = [b for b in self.all_backups if b['taken_at'].strftime('%Y-%m') == filter_text]
        
        backup_labels = [
            f"{b['taken_at'].strftime('%Y-%m-%d %H:%M:%S')} - {b['size_bytes']/1024:.1f}KB"
            for b in filtered_backups
        ]
        
        self.backup1_combo['values'] = backup_labels
        
        if len(backup_labels) >= 1:
            self.backup1_combo.current(0 if len(backup_labels) == 1 else 1)  # Older if multiple
        else:
            self.backup1_combo.set('')
        
        # Clear manual path when filter changes
        self.manual_before_path = None
    
    def _apply_after_filter(self):
        """Apply month filter to After backup list"""
        filter_text = self.after_month_var.get()
        
        if filter_text == "All":
            filtered_backups = self.all_backups
        else:
            filtered_backups = [b for b in self.all_backups if b['taken_at'].strftime('%Y-%m') == filter_text]
        
        backup_labels = [
            f"{b['taken_at'].strftime('%Y-%m-%d %H:%M:%S')} - {b['size_bytes']/1024:.1f}KB"
            for b in filtered_backups
        ]
        
        self.backup2_combo['values'] = backup_labels
        
        if len(backup_labels) >= 1:
            self.backup2_combo.current(0)  # Newer
        else:
            self.backup2_combo.set('')
        
        # Clear manual path when filter changes
        self.manual_after_path = None
    
    def _browse_before_file(self):
        """Browse and select a file for Before comparison"""
        file_path = filedialog.askopenfilename(
            title="Select Before File",
            filetypes=[("All files", "*.*"), ("Text files", "*.txt"), ("Config files", "*.cfg")]
        )
        
        if file_path:
            self.manual_before_path = file_path
            # Update combo to show manual selection
            self.backup1_combo.set(f"📁 Manual: {os.path.basename(file_path)}")
            Messagebox.show_info(f"Selected: {os.path.basename(file_path)}", "File Selected")
    
    def _browse_after_file(self):
        """Browse and select a file for After comparison"""
        file_path = filedialog.askopenfilename(
            title="Select After File",
            filetypes=[("All files", "*.*"), ("Text files", "*.txt"), ("Config files", "*.cfg")]
        )
        
        if file_path:
            self.manual_after_path = file_path
            # Update combo to show manual selection
            self.backup2_combo.set(f"📁 Manual: {os.path.basename(file_path)}")
            Messagebox.show_info(f"Selected: {os.path.basename(file_path)}", "File Selected")
    
    def _sync_scroll(self, event):
        """Synchronize scrolling between before and after views"""
        # Get the widget that triggered the event
        widget = event.widget
        
        # Scroll both text widgets
        self.before_text.yview_moveto(widget.yview()[0])
        self.after_text.yview_moveto(widget.yview()[0])
        
        return "break"
    
    def _select_latest(self):
        """Select latest vs previous backups"""
        if self.backup1_combo['values']:
            if len(self.backup1_combo['values']) >= 2:
                self.backup1_combo.current(1)
                self.backup2_combo.current(0)
                self._show_diff()
            else:
                Messagebox.show_warning("Need at least 2 backups", "Not Enough Backups")
    
    def _show_diff(self):
        """Show side-by-side diff between selected backups"""
        import difflib
        
        switch_name = self.switch_var.get()
        
        try:
            # Determine file paths for Before and After
            # Check if manual paths are set
            if self.manual_before_path:
                file_path1 = self.manual_before_path
                backup1_time = os.path.basename(file_path1)
            else:
                backup1_idx = self.backup1_combo.current()
                if backup1_idx < 0:
                    Messagebox.show_warning("Please select Before backup or browse a file", "Selection Required")
                    return
                
                # Use filtered backups based on Before month filter
                filter_text = self.before_month_var.get()
                if filter_text == "All":
                    filtered_backups = self.all_backups
                else:
                    filtered_backups = [b for b in self.all_backups if b['taken_at'].strftime('%Y-%m') == filter_text]
                
                backup1 = filtered_backups[backup1_idx]
                file_path1 = backup1['file_path']
                backup1_time = backup1['taken_at'].strftime("%Y-%m-%d %H:%M:%S")
            
            if self.manual_after_path:
                file_path2 = self.manual_after_path
                backup2_time = os.path.basename(file_path2)
            else:
                backup2_idx = self.backup2_combo.current()
                if backup2_idx < 0:
                    Messagebox.show_warning("Please select After backup or browse a file", "Selection Required")
                    return
                
                # Use filtered backups based on After month filter
                filter_text = self.after_month_var.get()
                if filter_text == "All":
                    filtered_backups = self.all_backups
                else:
                    filtered_backups = [b for b in self.all_backups if b['taken_at'].strftime('%Y-%m') == filter_text]
                
                backup2 = filtered_backups[backup2_idx]
                file_path2 = backup2['file_path']
                backup2_time = backup2['taken_at'].strftime("%Y-%m-%d %H:%M:%S")
            
            # Read contents from file paths
            with open(file_path1, 'r', encoding='utf-8') as f:
                content1 = f.read()
            with open(file_path2, 'r', encoding='utf-8') as f:
                content2 = f.read()
            
            # Get stats
            stats = self.diff_service.get_diff_stats(content1, content2)
            
            # Display stats
            self.stats_label.config(
                text=f"Added: {stats['added_lines']} | "
                     f"Removed: {stats['removed_lines']} | "
                     f"Changed: {stats['changed_lines']} | "
                     f"Total Changes: {stats['total_changes']}"
            )
            
            # Prepare side-by-side diff
            lines1 = content1.split('\n')
            lines2 = content2.split('\n')
            
            # Use SequenceMatcher to get line-by-line differences
            differ = difflib.SequenceMatcher(None, lines1, lines2)
            
            # Clear both text widgets
            self.before_text.config(state="normal")
            self.after_text.config(state="normal")
            self.before_text.delete("1.0", END)
            self.after_text.delete("1.0", END)
            
            line_num = 1
            
            # Process each operation
            for tag, i1, i2, j1, j2 in differ.get_opcodes():
                if tag == 'equal':
                    # Lines are the same
                    for i in range(i1, i2):
                        self.before_text.insert(END, f"{line_num:4d} | {lines1[i]}\n", "same")
                        self.after_text.insert(END, f"{line_num:4d} | {lines1[i]}\n", "same")
                        line_num += 1
                
                elif tag == 'replace':
                    # Lines were changed
                    max_lines = max(i2 - i1, j2 - j1)
                    for idx in range(max_lines):
                        # Before side
                        if idx < (i2 - i1):
                            self.before_text.insert(END, f"{line_num:4d} | {lines1[i1 + idx]}\n", "changed")
                        else:
                            self.before_text.insert(END, f"{line_num:4d} |\n", "same")
                        
                        # After side
                        if idx < (j2 - j1):
                            self.after_text.insert(END, f"{line_num:4d} | {lines2[j1 + idx]}\n", "changed")
                        else:
                            self.after_text.insert(END, f"{line_num:4d} |\n", "same")
                        
                        line_num += 1
                
                elif tag == 'delete':
                    # Lines were removed
                    for i in range(i1, i2):
                        self.before_text.insert(END, f"{line_num:4d} | {lines1[i]}\n", "removed")
                        self.after_text.insert(END, f"{line_num:4d} | [REMOVED]\n", "same")
                        line_num += 1
                
                elif tag == 'insert':
                    # Lines were added
                    for j in range(j1, j2):
                        self.before_text.insert(END, f"{line_num:4d} | [ADDED]\n", "same")
                        self.after_text.insert(END, f"{line_num:4d} | {lines2[j]}\n", "added")
                        line_num += 1
            
            self.before_text.config(state="disabled")
            self.after_text.config(state="disabled")
            
            # Save for export
            self.current_diff = self.diff_service.unified_diff(
                content1, content2,
                backup1_time,
                backup2_time
            )
                
        except Exception as e:
            Messagebox.show_error(f"Failed to generate diff: {e}", "Error")
            logger.exception("Diff generation failed")
    
    def _export_diff(self):
        """Export diff to file"""
        if not self.current_diff:
            Messagebox.show_warning("No diff to export. Generate diff first.", "No Diff")
            return
        
        dest_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if dest_path:
            if self.export_service.export_diff(self.current_diff, dest_path):
                Messagebox.show_info(f"Diff exported to {dest_path}", "Success")
