"""Schedules management view"""
import logging
from tkinter import END
from datetime import datetime, timedelta
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.data.repository import Repository
from app.services.schedule_service import ScheduleService
from app.config.paths import get_base_dir

logger = logging.getLogger(__name__)


class SchedulesView:
    """Backup schedules management view"""
    
    def __init__(self, parent, schedule_service: ScheduleService):
        self.parent = parent
        self.schedule_service = schedule_service
        
        self.frame = ttk.Frame(parent, padding=10)
        self._create_ui()
        self._load_data()
        
        # Auto-refresh every 10 seconds to update Last Run / Next Run
        self._start_auto_refresh()
    
    def _create_ui(self):
        """Create UI components"""
        # Toolbar
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill=X, pady=(0, 10))
        
        ttk.Button(
            toolbar,
            text="➕ Add Schedule",
            command=self._add_schedule,
            bootstyle=SUCCESS
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="✏️ Edit",
            command=self._edit_schedule,
            bootstyle=PRIMARY
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="🗑️ Delete",
            command=self._delete_schedule,
            bootstyle=DANGER
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="▶️ Enable",
            command=self._enable_schedule,
            bootstyle=SUCCESS
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="⏸️ Disable",
            command=self._disable_schedule,
            bootstyle=WARNING
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="▶️ Start Now",
            command=self._start_now,
            bootstyle=INFO
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="🔄 Refresh",
            command=self._load_data,
            bootstyle=SECONDARY
        ).pack(side=LEFT, padx=5)
        
        # Info frame for statistics
        info_frame = ttk.LabelFrame(self.frame, text="📊 Statistics", padding=10)
        info_frame.pack(fill=X, pady=(0, 10))
        
        self.stats_label = ttk.Label(
            info_frame,
            text="Total Schedules: 0 | Active: 0 | Successful Backups (Last 30 days): 0",
            font=("Segoe UI", 10)
        )
        self.stats_label.pack()
        
        # Table
        columns = ("ID", "Switch", "Interval", "Enabled", "Last Run", "Next Run")
        
        self.tree = ttk.Treeview(
            self.frame,
            columns=columns,
            show="headings",
            height=20
        )
        
        self.tree.column("ID", width=50, anchor=CENTER)
        self.tree.column("Switch", width=200)
        self.tree.column("Interval", width=150)
        self.tree.column("Enabled", width=80, anchor=CENTER)
        self.tree.column("Last Run", width=160)
        self.tree.column("Next Run", width=160)
        
        # Setup sortable columns
        self.sort_column = None
        self.sort_reverse = False
        
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by_column(c))
        
        # Configure row colors optimized for dark themes - vibrant text, no backgrounds
        self.tree.tag_configure('enabled', foreground='#4ade80')   # Bright green
        self.tree.tag_configure('disabled', foreground='#94a3b8')  # Light gray
        self.tree.tag_configure('pending', foreground='#fbbf24')   # Bright yellow
        
        scrollbar = ttk.Scrollbar(self.frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)
    
    def _load_data(self):
        """Load schedules"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        with Repository() as repo:
            jobs = repo.list_jobs()
            
            # Calculate statistics
            total_jobs = len(jobs)
            active_jobs = sum(1 for job in jobs if job.enabled)
            
            # Count successful backups in last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            all_backups = repo.list_backups()
            successful_backups = sum(
                1 for backup in all_backups 
                if backup.success and backup.taken_at >= thirty_days_ago
            )
            
            # Update statistics
            self.stats_label.config(
                text=f"Total Schedules: {total_jobs} | Active: {active_jobs} | "
                     f"Successful Backups (Last 30 days): {successful_backups}"
            )
            
            for job in jobs:
                interval_text = self._format_interval(job.interval_minutes)
                enabled_text = "✓" if job.enabled else "✗"
                last_run = job.last_ran_at.strftime("%Y-%m-%d %H:%M:%S") if job.last_ran_at else "Never"
                
                # Get next run from APScheduler (actual scheduled time)
                if job.enabled:
                    next_run_dt = self.schedule_service.get_next_run_time(job.id)
                    if next_run_dt:
                        # APScheduler returns naive local datetime now (converted in service)
                        try:
                            next_run = next_run_dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception as e:
                            logger.warning(f"Error formatting next_run_dt for job {job.id}: {e}")
                            next_run = str(next_run_dt)
                    else:
                        # Fallback calculation if not in scheduler yet
                        # Get stored time or default to 8:00 AM
                        stored_hour = getattr(job, 'schedule_hour', 8)
                        stored_minute = getattr(job, 'schedule_minute', 0)
                        
                        # For daily/weekly/monthly schedules, calculate next occurrence at specific time
                        if job.interval_minutes == 1440:  # Daily
                            # Calculate next day at stored time
                            now = datetime.now()
                            next_run_time = now.replace(hour=stored_hour, minute=stored_minute, second=0, microsecond=0)
                            if next_run_time <= now:
                                next_run_time += timedelta(days=1)
                            next_run = next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                        elif job.interval_minutes == 10080:  # Weekly
                            # Calculate next week same day/time
                            now = datetime.now()
                            next_run_time = now.replace(hour=stored_hour, minute=stored_minute, second=0, microsecond=0)
                            days_ahead = 7 - now.weekday()  # Days until next Monday
                            if days_ahead <= 0 or (days_ahead == 0 and next_run_time <= now):
                                days_ahead += 7
                            next_run_time = now + timedelta(days=days_ahead)
                            next_run = next_run_time.replace(hour=stored_hour, minute=stored_minute, second=0).strftime("%Y-%m-%d %H:%M:%S")
                        elif job.interval_minutes == 43200:  # Monthly
                            # Calculate next month same day/time
                            now = datetime.now()
                            next_run_time = now.replace(day=1, hour=stored_hour, minute=stored_minute, second=0, microsecond=0)
                            if next_run_time <= now:
                                # Next month
                                if now.month == 12:
                                    next_run_time = next_run_time.replace(year=now.year + 1, month=1)
                                else:
                                    next_run_time = next_run_time.replace(month=now.month + 1)
                            next_run = next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            # Interval-based schedule
                            if job.last_ran_at:
                                next_run_time = job.last_ran_at + timedelta(minutes=job.interval_minutes)
                                # Check if calculated time is in the past
                                now = datetime.now()
                                if next_run_time < now:
                                    # Calculate how many intervals have passed and get next one
                                    time_diff = (now - job.last_ran_at).total_seconds() / 60
                                    intervals_passed = int(time_diff / job.interval_minutes)
                                    next_run_time = job.last_ran_at + timedelta(minutes=job.interval_minutes * (intervals_passed + 1))
                                next_run = next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                next_run = "Soon"
                else:
                    next_run = "Disabled"
                
                # Determine color tag
                tag = ''
                if job.enabled:
                    if next_run == 'Soon':
                        tag = 'pending'
                    else:
                        tag = 'enabled'
                else:
                    tag = 'disabled'
                
                self.tree.insert("", END, values=(
                    job.id,
                    job.switch.name,
                    interval_text,
                    enabled_text,
                    last_run,
                    next_run
                ), tags=(tag,))
    
    def _format_interval(self, minutes: int) -> str:
        """Format interval for display"""
        if minutes < 60:
            return f"Every {minutes} minutes"
        elif minutes < 1440:
            hours = minutes // 60
            return f"Every {hours} hour{'s' if hours > 1 else ''}"
        else:
            days = minutes // 1440
            return f"Every {days} day{'s' if days > 1 else ''}"
    
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
        elif col in ('Last Run', 'Next Run'):
            # Date/time sort (handles "Never", "Disabled", "Soon" etc.)
            def parse_datetime(val):
                if val in ('Never', 'Disabled', 'Soon'):
                    return '9999-99-99'  # Sort these to end
                return val
            items.sort(key=lambda x: parse_datetime(x[0]), reverse=self.sort_reverse)
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
        """Start auto-refresh timer"""
        self._auto_refresh()
    
    def _auto_refresh(self):
        """Auto-refresh schedules table every 10 seconds"""
        try:
            # Store current selection
            selected_items = self.tree.selection()
            selected_id = None
            if selected_items:
                selected_id = self.tree.item(selected_items[0])['values'][0]
            
            # Reload data
            self._load_data()
            
            # Restore selection
            if selected_id:
                for item in self.tree.get_children():
                    if self.tree.item(item)['values'][0] == selected_id:
                        self.tree.selection_set(item)
                        break
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
        
        # Schedule next refresh in 10 seconds
        self.frame.after(10000, self._auto_refresh)
    
    def _add_schedule(self):
        """Add new schedule"""
        ScheduleDialog(self.frame, self.schedule_service, callback=self._load_data)
    
    def _edit_schedule(self):
        """Edit selected schedule"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a schedule to edit", "No Selection")
            return
        
        job_id = self.tree.item(selected[0])['values'][0]
        ScheduleDialog(self.frame, self.schedule_service, job_id=job_id, callback=self._load_data)
    
    def _delete_schedule(self):
        """Delete selected schedule"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a schedule to delete", "No Selection")
            return
        
        if not Messagebox.show_question("Delete this schedule?", "Confirm Delete"):
            return
        
        job_id = self.tree.item(selected[0])['values'][0]
        
        try:
            self.schedule_service.remove_job(job_id)
            
            with Repository() as repo:
                repo.delete_job(job_id)
            
            Messagebox.show_info("Schedule deleted", "Success")
            self._load_data()
        except Exception as e:
            Messagebox.show_error(f"Failed to delete schedule: {e}", "Error")
    
    def _enable_schedule(self):
        """Enable selected schedule"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a schedule", "No Selection")
            return
        
        job_id = self.tree.item(selected[0])['values'][0]
        
        try:
            # Get job details from database
            with Repository() as repo:
                job = repo.get_job(job_id)
                if not job:
                    Messagebox.show_error("Job not found", "Error")
                    return
                
                switch_id = job.switch_id
                interval_minutes = job.interval_minutes
                schedule_hour = getattr(job, 'schedule_hour', 8)
                schedule_minute = getattr(job, 'schedule_minute', 0)
                
                # Update enabled status
                repo.update_job(job_id, enabled=True)
            
            # Check if job exists in scheduler
            if job_id in self.schedule_service.job_map:
                # Job exists, just resume it
                self.schedule_service.resume_job(job_id)
                logger.info(f"Resumed existing job {job_id} in scheduler")
            else:
                # Job not in scheduler (maybe service restarted), add it
                self.schedule_service.add_job(job_id, switch_id, interval_minutes, schedule_hour, schedule_minute)
                logger.info(f"Added job {job_id} to scheduler (was not present)")
            
            Messagebox.show_info("Schedule enabled", "Success")
            self._load_data()
        except Exception as e:
            Messagebox.show_error(f"Failed to enable schedule: {e}", "Error")
            logger.exception(f"Failed to enable schedule {job_id}")
    
    def _disable_schedule(self):
        """Disable selected schedule"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a schedule", "No Selection")
            return
        
        job_id = self.tree.item(selected[0])['values'][0]
        
        try:
            with Repository() as repo:
                repo.update_job(job_id, enabled=False)
            
            # Only pause if job exists in scheduler
            if job_id in self.schedule_service.job_map:
                self.schedule_service.pause_job(job_id)
                logger.info(f"Paused job {job_id} in scheduler")
            else:
                logger.info(f"Job {job_id} not in scheduler, only updated database")
            
            Messagebox.show_info("Schedule disabled", "Success")
            self._load_data()
        except Exception as e:
            Messagebox.show_error(f"Failed to disable schedule: {e}", "Error")
            logger.exception(f"Failed to disable schedule {job_id}")
    
    def _start_now(self):
        """Manually trigger selected schedule(s) now - supports multiple selection"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select one or more schedules", "No Selection")
            return
        
        # Collect all selected jobs
        jobs_to_run = []
        for item in selected:
            job_id = self.tree.item(item)['values'][0]
            switch_name = self.tree.item(item)['values'][1]
            jobs_to_run.append((job_id, switch_name))
        
        # Confirm action
        if len(jobs_to_run) == 1:
            message = f"Start backup now for {jobs_to_run[0][1]}?"
        else:
            switches_list = ", ".join([name for _, name in jobs_to_run])
            message = f"Start backup now for {len(jobs_to_run)} switches?\n\n{switches_list}\n\nJobs will run one by one."
        
        result = Messagebox.yesno(message, "Confirm Manual Start")
        
        if result != "Yes":
            return
        
        try:
            # Get job details for all selected jobs
            jobs_data = []
            with Repository() as repo:
                for job_id, _ in jobs_to_run:
                    job = repo.get_job(job_id)
                    if job:
                        jobs_data.append({
                            'job_id': job_id,
                            'switch_id': job.switch_id,
                            'switch_name': job.switch.name
                        })
            
            if not jobs_data:
                Messagebox.show_error("No valid jobs found", "Error")
                return
            
            # Execute backups manually (outside session context)
            from app.services.backup_service import BackupService
            backup_service = BackupService(self.schedule_service.crypto)
            
            Messagebox.show_info(
                f"Starting {len(jobs_data)} backup(s).\nJobs will execute one by one.\nCheck system console for progress.",
                "Backups Started"
            )
            
            # Run in background thread, executing jobs sequentially
            import threading
            def run_backups_sequentially():
                for idx, job_data in enumerate(jobs_data, 1):
                    try:
                        job_id = job_data['job_id']
                        switch_id = job_data['switch_id']
                        switch_name = job_data['switch_name']
                        
                        logger.info(f"[MANUAL {idx}/{len(jobs_data)}] Starting backup for {switch_name}")
                        
                        # Execute backup with manual type
                        result = backup_service.execute_backup(switch_id, backup_type='manual')
                        logger.info(f"[MANUAL {idx}/{len(jobs_data)}] {switch_name}: {result['message']}")
                        
                        # Update last run time
                        from datetime import datetime
                        with Repository() as repo:
                            repo.update_job(job_id, last_ran_at=datetime.now())
                            
                    except Exception as e:
                        logger.exception(f"Manual schedule run failed for job {job_id}")
                
                logger.info(f"[MANUAL] Completed all {len(jobs_data)} backup(s)")
            
            thread = threading.Thread(target=run_backups_sequentially, daemon=True)
            thread.start()
            
            # Refresh after a moment
            self.frame.after(1000, self._load_data)
                
        except Exception as e:
            Messagebox.show_error(f"Failed to start backups: {e}", "Error")
            logger.exception("Failed to manually start schedules")


class ScheduleDialog:
    """Dialog for adding/editing schedules"""
    
    def __init__(self, parent, schedule_service, job_id=None, callback=None):
        self.schedule_service = schedule_service
        self.job_id = job_id
        self.callback = callback
        
        self.dialog = ttk.Toplevel(parent)
        self.dialog.title("Edit Schedule" if job_id else "Add Schedule")
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_ui()
        
        if job_id:
            self._load_job_data()
    
    def _create_ui(self):
        """Create dialog UI"""
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill=BOTH, expand=YES)
        
        # Switch
        ttk.Label(frame, text="Switch:").grid(row=0, column=0, sticky=W, pady=5)
        self.switch_var = ttk.StringVar()
        
        with Repository() as repo:
            switches = repo.list_switches()
            switch_names = [s.name for s in switches]
        
        self.switch_combo = ttk.Combobox(frame, textvariable=self.switch_var, values=switch_names, state="readonly", width=35)
        self.switch_combo.grid(row=0, column=1, columnspan=2, pady=5, sticky=W)
        if switch_names:
            self.switch_combo.current(0)
        
        # Schedule Type
        ttk.Label(frame, text="Schedule Type:").grid(row=1, column=0, sticky=W, pady=10)
        self.schedule_type = ttk.StringVar(value="interval")
        
        type_frame = ttk.Frame(frame)
        type_frame.grid(row=1, column=1, columnspan=2, sticky=W, pady=10)
        
        ttk.Radiobutton(type_frame, text="Interval", variable=self.schedule_type, value="interval", command=self._toggle_schedule_type).pack(side=LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Daily", variable=self.schedule_type, value="daily", command=self._toggle_schedule_type).pack(side=LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Weekly", variable=self.schedule_type, value="weekly", command=self._toggle_schedule_type).pack(side=LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Monthly", variable=self.schedule_type, value="monthly", command=self._toggle_schedule_type).pack(side=LEFT, padx=5)
        
        # Interval Options (hidden/shown based on type)
        self.interval_frame = ttk.LabelFrame(frame, text="Interval Options", padding=10)
        self.interval_frame.grid(row=2, column=0, columnspan=3, sticky=EW, pady=10)
        
        self.interval_var = ttk.IntVar(value=60)
        intervals = [
            ("Every 15 minutes", 15),
            ("Every 30 minutes", 30),
            ("Every hour", 60),
            ("Every 6 hours", 360),
            ("Every 12 hours", 720),
            ("Custom minutes", 0)  # 0 = custom
        ]
        
        for text, value in intervals:
            ttk.Radiobutton(
                self.interval_frame,
                text=text,
                variable=self.interval_var,
                value=value,
                command=self._on_interval_change
            ).pack(anchor=W, pady=2)
        
        # Custom minutes input (initially hidden)
        custom_frame = ttk.Frame(self.interval_frame)
        custom_frame.pack(anchor=W, pady=5, padx=20)
        
        ttk.Label(custom_frame, text="Custom interval (minutes):").pack(side=LEFT, padx=5)
        self.custom_minutes_var = ttk.IntVar(value=5)
        self.custom_minutes_entry = ttk.Entry(
            custom_frame,
            textvariable=self.custom_minutes_var,
            width=10,
            state="disabled"
        )
        self.custom_minutes_entry.pack(side=LEFT)
        
        ttk.Label(custom_frame, text="(1-1440 minutes)", font=("Segoe UI", 8)).pack(side=LEFT, padx=5)
        
        # Daily Options
        self.daily_frame = ttk.LabelFrame(frame, text="Daily Options", padding=10)
        self.daily_frame.grid(row=2, column=0, columnspan=3, sticky=EW, pady=10)
        
        ttk.Label(self.daily_frame, text="Time (24-hour):").pack(side=LEFT, padx=5)
        self.daily_hour = ttk.Spinbox(self.daily_frame, from_=0, to=23, width=5)
        self.daily_hour.set("0")
        self.daily_hour.pack(side=LEFT, padx=2)
        ttk.Label(self.daily_frame, text=":").pack(side=LEFT)
        self.daily_minute = ttk.Spinbox(self.daily_frame, from_=0, to=59, width=5)
        self.daily_minute.set("0")
        self.daily_minute.pack(side=LEFT, padx=2)
        
        # Weekly Options
        self.weekly_frame = ttk.LabelFrame(frame, text="Weekly Options", padding=10)
        self.weekly_frame.grid(row=2, column=0, columnspan=3, sticky=EW, pady=10)
        
        ttk.Label(self.weekly_frame, text="Day:").pack(side=LEFT, padx=5)
        self.weekly_day = ttk.Combobox(self.weekly_frame, values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], state="readonly", width=12)
        self.weekly_day.current(0)
        self.weekly_day.pack(side=LEFT, padx=5)
        ttk.Label(self.weekly_frame, text="Time:").pack(side=LEFT, padx=5)
        self.weekly_hour = ttk.Spinbox(self.weekly_frame, from_=0, to=23, width=5)
        self.weekly_hour.set("0")
        self.weekly_hour.pack(side=LEFT, padx=2)
        ttk.Label(self.weekly_frame, text=":").pack(side=LEFT)
        self.weekly_minute = ttk.Spinbox(self.weekly_frame, from_=0, to=59, width=5)
        self.weekly_minute.set("0")
        self.weekly_minute.pack(side=LEFT, padx=2)
        
        # Monthly Options
        self.monthly_frame = ttk.LabelFrame(frame, text="Monthly Options", padding=10)
        self.monthly_frame.grid(row=2, column=0, columnspan=3, sticky=EW, pady=10)
        
        ttk.Label(self.monthly_frame, text="Day of Month:").pack(side=LEFT, padx=5)
        self.monthly_day = ttk.Spinbox(self.monthly_frame, from_=1, to=31, width=5)
        self.monthly_day.set("1")
        self.monthly_day.pack(side=LEFT, padx=5)
        ttk.Label(self.monthly_frame, text="Time:").pack(side=LEFT, padx=5)
        self.monthly_hour = ttk.Spinbox(self.monthly_frame, from_=0, to=23, width=5)
        self.monthly_hour.set("0")
        self.monthly_hour.pack(side=LEFT, padx=2)
        ttk.Label(self.monthly_frame, text=":").pack(side=LEFT)
        self.monthly_minute = ttk.Spinbox(self.monthly_frame, from_=0, to=59, width=5)
        self.monthly_minute.set("0")
        self.monthly_minute.pack(side=LEFT, padx=2)
        
        # Hide all except interval by default
        self._toggle_schedule_type()
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        ttk.Button(btn_frame, text="Save", command=self._save, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy, bootstyle=SECONDARY).pack(side=LEFT, padx=5)
    
    def _on_interval_change(self):
        """Enable/disable custom minutes input based on selection"""
        if self.interval_var.get() == 0:  # Custom
            self.custom_minutes_entry.config(state="normal")
        else:
            self.custom_minutes_entry.config(state="disabled")
    
    def _toggle_schedule_type(self):
        """Show/hide schedule options based on type"""
        schedule_type = self.schedule_type.get()
        
        # Hide all frames
        self.interval_frame.grid_remove()
        self.daily_frame.grid_remove()
        self.weekly_frame.grid_remove()
        self.monthly_frame.grid_remove()
        
        # Show selected frame
        if schedule_type == "interval":
            self.interval_frame.grid()
        elif schedule_type == "daily":
            self.daily_frame.grid()
        elif schedule_type == "weekly":
            self.weekly_frame.grid()
        elif schedule_type == "monthly":
            self.monthly_frame.grid()
    
    def _set_schedule_time_directly(self, job_id, schedule_hour, schedule_minute):
        """Set schedule time using direct SQL (workaround for non-mapped columns)"""
        import sqlite3
        from pathlib import Path
        
        base_dir = get_base_dir()
        db_path = base_dir / "data" / "app.db"
        
        try:
            conn = sqlite3.connect(str(db_path.absolute()))
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE jobs 
                SET schedule_hour = ?, schedule_minute = ?
                WHERE id = ?
            """, (schedule_hour, schedule_minute, job_id))
            conn.commit()
            conn.close()
            logger.info(f"Schedule time set for job {job_id}: {schedule_hour}:{schedule_minute}")
        except Exception as e:
            logger.error(f"Failed to set schedule time directly: {e}")
            logger.error(f"Database path attempted: {db_path}")
            raise
    
    def _load_job_data(self):
        """Load existing job data"""
        with Repository() as repo:
            job = repo.get_job(self.job_id)
            if job:
                self.switch_var.set(job.switch.name)
                self.interval_var.set(job.interval_minutes)
                
                # Load schedule time if available
                schedule_hour = getattr(job, 'schedule_hour', 8)
                schedule_minute = getattr(job, 'schedule_minute', 0)
                
                # Set the time fields based on interval type
                if job.interval_minutes == 1440:  # Daily
                    self.schedule_type.set("daily")
                    self.daily_hour.set(str(schedule_hour))
                    self.daily_minute.set(str(schedule_minute))
                elif job.interval_minutes == 10080:  # Weekly
                    self.schedule_type.set("weekly")
                    self.weekly_hour.set(str(schedule_hour))
                    self.weekly_minute.set(str(schedule_minute))
                elif job.interval_minutes == 43200:  # Monthly
                    self.schedule_type.set("monthly")
                    self.monthly_hour.set(str(schedule_hour))
                    self.monthly_minute.set(str(schedule_minute))
                else:
                    self.schedule_type.set("interval")
                
                self._toggle_schedule_type()
    
    def _save(self):
        """Save schedule"""
        switch_name = self.switch_var.get()
        
        if not switch_name:
            Messagebox.show_error("Please select a switch", "Validation Error")
            return
        
        # Calculate interval and time based on schedule type
        schedule_type = self.schedule_type.get()
        schedule_hour = 8  # Default
        schedule_minute = 0  # Default
        
        if schedule_type == "interval":
            interval = self.interval_var.get()
            if interval == 0:  # Custom minutes
                interval = self.custom_minutes_var.get()
                if interval < 1 or interval > 1440:
                    Messagebox.show_error("Custom interval must be between 1 and 1440 minutes", "Invalid Input")
                    return
        elif schedule_type == "daily":
            # Daily = 1440 minutes (24 hours)
            interval = 1440
            schedule_hour = int(self.daily_hour.get())
            schedule_minute = int(self.daily_minute.get())
        elif schedule_type == "weekly":
            # Weekly = 10080 minutes (7 days)
            interval = 10080
            schedule_hour = int(self.weekly_hour.get())
            schedule_minute = int(self.weekly_minute.get())
        elif schedule_type == "monthly":
            # Monthly = 43200 minutes (30 days)
            interval = 43200
            schedule_hour = int(self.monthly_hour.get())
            schedule_minute = int(self.monthly_minute.get())
        
        try:
            # First, create or update the job
            with Repository() as repo:
                switch = repo.get_switch_by_name(switch_name)
                if not switch:
                    Messagebox.show_error("Switch not found", "Error")
                    return
                
                if self.job_id:
                    # Update existing job
                    try:
                        repo.update_job(self.job_id, interval_minutes=interval, schedule_hour=schedule_hour, schedule_minute=schedule_minute)
                        needs_time_update = False
                    except TypeError:
                        # If repository doesn't support schedule_hour/minute, update them separately
                        repo.update_job(self.job_id, interval_minutes=interval)
                        needs_time_update = True
                    
                    job_id = self.job_id
                    switch_id = switch.id
                else:
                    # Create new job
                    job = repo.create_job(switch.id, interval, enabled=True)
                    job_id = job.id
                    switch_id = switch.id
                    needs_time_update = True
            
            # Now update schedule time AFTER repository is closed (to avoid database lock)
            if needs_time_update:
                self._set_schedule_time_directly(job_id, schedule_hour, schedule_minute)
            
            # Add job to scheduler
            if self.job_id:
                self.schedule_service.remove_job(job_id)
            self.schedule_service.add_job(job_id, switch_id, interval, schedule_hour, schedule_minute)
            
            # Show summary
            type_desc = {
                "interval": f"Every {interval} minutes",
                "daily": f"Daily at {self.daily_hour.get()}:{int(self.daily_minute.get()):02d}",
                "weekly": f"Weekly on {self.weekly_day.get()} at {self.weekly_hour.get()}:{int(self.weekly_minute.get()):02d}",
                "monthly": f"Monthly on day {self.monthly_day.get()} at {self.monthly_hour.get()}:{int(self.monthly_minute.get()):02d}"
            }
            
            Messagebox.show_info(
                f"Schedule saved successfully!\n\n{type_desc.get(schedule_type, 'Schedule configured')}\n\nNext run time will update shortly.",
                "Success"
            )
            self.dialog.destroy()
            
            if self.callback:
                # Immediate refresh
                self.callback()
                # Schedule multiple refreshes to ensure next run time updates from APScheduler
                self.dialog.master.after(100, self.callback)   # 0.1 seconds - very quick
                self.dialog.master.after(500, self.callback)   # 0.5 seconds
                self.dialog.master.after(1500, self.callback)  # 1.5 seconds
                self.dialog.master.after(3000, self.callback)  # 3 seconds
                self.dialog.master.after(6000, self.callback)  # 6 seconds - final check
        
        except Exception as e:
            Messagebox.show_error(f"Failed to save schedule: {e}", "Error")
