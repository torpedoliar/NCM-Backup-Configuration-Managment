"""Schedules management view"""
import csv
import io
import logging
from dataclasses import dataclass
from tkinter import END
from datetime import datetime, timedelta
from typing import List
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.data.repository import Repository
from app.services.schedule_service import ScheduleService
from app.config.paths import get_base_dir

logger = logging.getLogger(__name__)

SCHEDULE_BULK_COLUMNS = ("switch_name", "schedule_type", "interval_minutes", "hour", "minute", "enabled")
VALID_SCHEDULE_TYPES = {"interval", "daily", "weekly", "monthly"}
NAMED_SCHEDULE_INTERVALS = {
    "daily": 1440,
    "weekly": 10080,
    "monthly": 43200,
}
TRUE_VALUES = {"", "true", "yes", "1", "y", "enabled"}
FALSE_VALUES = {"false", "no", "0", "n", "disabled"}


@dataclass
class ScheduleBulkRow:
    row_num: int
    switch_name: str
    schedule_type: str
    interval_minutes: int
    schedule_hour: int
    schedule_minute: int
    enabled: bool


@dataclass
class ScheduleBulkParseResult:
    rows: List[ScheduleBulkRow]
    errors: List[str]


def _is_schedule_header(values: List[str]) -> bool:
    normalized = {value.strip().lower() for value in values}
    return "switch_name" in normalized and "schedule_type" in normalized


def _schedule_record_from_values(values: List[str]) -> dict:
    return {
        column: values[index].strip() if index < len(values) else ""
        for index, column in enumerate(SCHEDULE_BULK_COLUMNS)
    }


def _parse_int_range(value: str, minimum: int, maximum: int) -> int:
    parsed = int(value)
    if not minimum <= parsed <= maximum:
        raise ValueError
    return parsed


def parse_schedule_bulk_text(text: str) -> ScheduleBulkParseResult:
    csv_rows = [
        row for row in csv.reader(io.StringIO(text))
        if any(cell.strip() for cell in row)
    ]
    if not csv_rows:
        return ScheduleBulkParseResult(rows=[], errors=["No rows found"])

    has_header = _is_schedule_header(csv_rows[0])
    header = [cell.strip().lower() for cell in csv_rows[0]] if has_header else []
    data_rows = csv_rows[1:] if has_header else csv_rows
    first_row_num = 2 if has_header else 1

    parsed_rows = []
    errors = []

    for offset, values in enumerate(data_rows):
        row_num = first_row_num + offset
        if has_header:
            record = {
                header[index]: values[index].strip() if index < len(values) else ""
                for index in range(len(header))
            }
        else:
            record = _schedule_record_from_values(values)

        switch_name = record.get("switch_name", "").strip()
        schedule_type = record.get("schedule_type", "").strip().lower()
        interval_text = record.get("interval_minutes", "").strip()
        hour_text = record.get("hour", "").strip()
        minute_text = record.get("minute", "").strip()
        enabled_text = record.get("enabled", "").strip().lower()

        if not switch_name:
            errors.append(f"Row {row_num}: Missing switch name")
            continue
        if schedule_type not in VALID_SCHEDULE_TYPES:
            errors.append(f"Row {row_num}: Invalid schedule type '{schedule_type}'")
            continue

        if schedule_type == "interval":
            if not interval_text:
                errors.append(f"Row {row_num}: Missing interval minutes")
                continue
            try:
                interval_minutes = _parse_int_range(interval_text, 1, 43200)
            except ValueError:
                errors.append(f"Row {row_num}: Invalid interval minutes '{interval_text}'")
                continue
        else:
            interval_minutes = NAMED_SCHEDULE_INTERVALS[schedule_type]

        try:
            schedule_hour = _parse_int_range(hour_text or "8", 0, 23)
        except ValueError:
            errors.append(f"Row {row_num}: Invalid hour '{hour_text}'")
            continue

        try:
            schedule_minute = _parse_int_range(minute_text or "0", 0, 59)
        except ValueError:
            errors.append(f"Row {row_num}: Invalid minute '{minute_text}'")
            continue

        if enabled_text in TRUE_VALUES:
            enabled = True
        elif enabled_text in FALSE_VALUES:
            enabled = False
        else:
            errors.append(f"Row {row_num}: Invalid enabled value '{enabled_text}'")
            continue

        parsed_rows.append(ScheduleBulkRow(
            row_num=row_num,
            switch_name=switch_name,
            schedule_type=schedule_type,
            interval_minutes=interval_minutes,
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
            enabled=enabled,
        ))

    return ScheduleBulkParseResult(rows=parsed_rows, errors=errors)


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
            text="➕ Bulk Add",
            command=self._bulk_add_schedule,
            bootstyle=SUCCESS
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="📋 Import CSV",
            command=self._import_schedules_csv,
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
            height=20,
            selectmode="extended"
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
            selected_ids = []
            for item in self.tree.selection():
                values = self.tree.item(item)['values']
                if values:
                    selected_ids.append(values[0])

            self._load_data()

            restored_items = []
            for item in self.tree.get_children():
                values = self.tree.item(item)['values']
                if values and values[0] in selected_ids:
                    restored_items.append(item)
            if restored_items:
                self.tree.selection_set(restored_items)
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
        
        # Schedule next refresh in 10 seconds
        self.frame.after(10000, self._auto_refresh)
    
    def _get_selected_job_rows(self):
        rows = []
        for item in self.tree.selection():
            values = self.tree.item(item)['values']
            rows.append({
                'id': int(values[0]),
                'switch_name': values[1],
            })
        return rows

    def _format_name_preview(self, names):
        preview = ", ".join(names[:8])
        if len(names) > 8:
            preview += f", ... and {len(names) - 8} more"
        return preview

    def _format_bulk_result(self, title, created=0, updated=0, skipped=0, failed=0, errors=None):
        errors = errors or []
        message = (
            f"{title}\n\n"
            f"Created: {created}\n"
            f"Updated: {updated}\n"
            f"Skipped: {skipped}\n"
            f"Failed: {failed}"
        )
        if errors:
            message += "\n\nErrors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                message += f"\n... and {len(errors) - 10} more errors"
        return message

    def _ask_duplicate_mode(self, duplicate_count, item_label):
        result = Messagebox.yesno(
            f"Found {duplicate_count} duplicate {item_label}.\n\n"
            "Choose Yes to update existing records.\n"
            "Choose No to skip duplicates.",
            "Duplicates Found"
        )
        return "update" if result == "Yes" else "skip"

    def _find_duplicate_job(self, jobs, switch_id, interval_minutes, schedule_hour, schedule_minute):
        for job in jobs:
            if (
                job.switch_id == switch_id
                and job.interval_minutes == interval_minutes
                and getattr(job, 'schedule_hour', 8) == schedule_hour
                and getattr(job, 'schedule_minute', 0) == schedule_minute
            ):
                return job
        return None

    def _add_schedule(self):
        """Add new schedule"""
        ScheduleDialog(self.frame, self.schedule_service, callback=self._load_data)

    def _bulk_add_schedule(self):
        """Add one schedule configuration to multiple switches"""
        ScheduleDialog(self.frame, self.schedule_service, callback=self._load_data, bulk=True)

    def _import_schedules_csv(self):
        """Import schedules from CSV file"""
        from tkinter import filedialog

        filename = filedialog.askopenfilename(
            title="Select CSV File to Import Schedules",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return

        instructions = (
            "CSV Format Expected:\n\n"
            "switch_name,schedule_type,interval_minutes,hour,minute,enabled\n\n"
            "Examples:\n"
            "Switch01,interval,60,8,0,true\n"
            "Switch02,daily,,9,30,true\n\n"
            "switch_name must match an existing switch."
        )
        if not Messagebox.show_question(instructions + "\n\nContinue with import?", "Schedule CSV Import Format"):
            return

        try:
            with open(filename, 'r', encoding='utf-8') as csvfile:
                self._import_schedule_bulk_text(csvfile.read(), filename)
        except Exception as e:
            Messagebox.show_error(f"Failed to read CSV: {e}", "Import Error")
            logger.exception("Schedule CSV import failed")

    def _import_schedule_bulk_text(self, text, source_name):
        parse_result = parse_schedule_bulk_text(text)
        errors = list(parse_result.errors)
        if not parse_result.rows:
            Messagebox.show_warning(
                self._format_bulk_result(f"No schedules imported from {source_name}.", failed=len(errors), errors=errors),
                "Import Complete"
            )
            return

        created = 0
        updated = 0
        skipped = 0
        jobs_to_schedule = []

        try:
            with Repository() as repo:
                switches = {switch.name: switch for switch in repo.list_switches()}
                jobs = repo.list_jobs()
                duplicate_count = 0

                for row in parse_result.rows:
                    switch = switches.get(row.switch_name)
                    if not switch:
                        errors.append(f"Row {row.row_num}: Switch '{row.switch_name}' not found")
                        continue
                    if self._find_duplicate_job(jobs, switch.id, row.interval_minutes, row.schedule_hour, row.schedule_minute):
                        duplicate_count += 1

                duplicate_mode = "skip"
                if duplicate_count:
                    duplicate_mode = self._ask_duplicate_mode(duplicate_count, "schedule(s)")

                for row in parse_result.rows:
                    switch = switches.get(row.switch_name)
                    if not switch:
                        skipped += 1
                        continue
                    duplicate = self._find_duplicate_job(jobs, switch.id, row.interval_minutes, row.schedule_hour, row.schedule_minute)
                    if duplicate:
                        if duplicate_mode == "skip":
                            skipped += 1
                            continue
                        repo.update_job(
                            duplicate.id,
                            interval_minutes=row.interval_minutes,
                            enabled=row.enabled,
                            schedule_hour=row.schedule_hour,
                            schedule_minute=row.schedule_minute,
                        )
                        jobs_to_schedule.append((duplicate.id, switch.id, row.interval_minutes, row.schedule_hour, row.schedule_minute, row.enabled))
                        updated += 1
                    else:
                        job = repo.create_job(switch.id, row.interval_minutes, enabled=row.enabled)
                        job.schedule_hour = row.schedule_hour
                        job.schedule_minute = row.schedule_minute
                        jobs.append(job)
                        jobs_to_schedule.append((job.id, switch.id, row.interval_minutes, row.schedule_hour, row.schedule_minute, row.enabled))
                        created += 1

            for job_id, switch_id, interval_minutes, schedule_hour, schedule_minute, enabled in jobs_to_schedule:
                if enabled:
                    self.schedule_service.add_job(job_id, switch_id, interval_minutes, schedule_hour, schedule_minute)
                elif job_id in self.schedule_service.job_map:
                    self.schedule_service.remove_job(job_id)

            message = self._format_bulk_result(
                f"Schedule import completed from {source_name}.",
                created=created,
                updated=updated,
                skipped=skipped,
                failed=len(errors),
                errors=errors,
            )
            if created or updated:
                Messagebox.show_info(message, "Import Complete")
            else:
                Messagebox.show_warning(message, "Import Complete")
            self._load_data()
        except Exception as e:
            Messagebox.show_error(f"Failed to import schedules: {e}", "Import Error")
            logger.exception("Bulk schedule import failed")

    def _edit_schedule(self):
        """Edit selected schedule"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a schedule to edit", "No Selection")
            return
        
        job_id = self.tree.item(selected[0])['values'][0]
        ScheduleDialog(self.frame, self.schedule_service, job_id=job_id, callback=self._load_data)
    
    def _delete_schedule(self):
        """Delete selected schedules"""
        rows = self._get_selected_job_rows()
        if not rows:
            Messagebox.show_warning("Please select one or more schedules to delete", "No Selection")
            return

        names = [row['switch_name'] for row in rows]
        message = (
            f"Delete {len(rows)} schedule(s)?\n\n"
            f"{self._format_name_preview(names)}"
        )
        if not Messagebox.show_question(message, "Confirm Delete"):
            return

        deleted = 0
        errors = []
        for row in rows:
            try:
                if row['id'] in self.schedule_service.job_map:
                    self.schedule_service.remove_job(row['id'])
                with Repository() as repo:
                    if repo.delete_job(row['id']):
                        deleted += 1
                    else:
                        errors.append(f"Schedule not found for {row['switch_name']}")
            except Exception as e:
                errors.append(f"{row['switch_name']}: {e}")

        message = self._format_bulk_result(
            "Schedule delete completed.",
            updated=deleted,
            failed=len(errors),
            errors=errors,
        ).replace("Updated", "Deleted")
        if errors:
            Messagebox.show_warning(message, "Delete Complete")
        else:
            Messagebox.show_info(message, "Delete Complete")
        self._load_data()

    def _enable_schedule(self):
        """Enable selected schedules"""
        rows = self._get_selected_job_rows()
        if not rows:
            Messagebox.show_warning("Please select one or more schedules", "No Selection")
            return

        enabled = 0
        errors = []
        jobs_to_schedule = []

        for row in rows:
            try:
                with Repository() as repo:
                    job = repo.get_job(row['id'])
                    if not job:
                        errors.append(f"Schedule not found for {row['switch_name']}")
                        continue
                    schedule_hour = getattr(job, 'schedule_hour', 8)
                    schedule_minute = getattr(job, 'schedule_minute', 0)
                    switch_id = job.switch_id
                    interval_minutes = job.interval_minutes
                    repo.update_job(row['id'], enabled=True)
                    jobs_to_schedule.append((row['id'], switch_id, interval_minutes, schedule_hour, schedule_minute))
                    enabled += 1
            except Exception as e:
                errors.append(f"{row['switch_name']}: {e}")

        for job_id, switch_id, interval_minutes, schedule_hour, schedule_minute in jobs_to_schedule:
            try:
                if job_id in self.schedule_service.job_map:
                    self.schedule_service.resume_job(job_id)
                else:
                    self.schedule_service.add_job(job_id, switch_id, interval_minutes, schedule_hour, schedule_minute)
            except Exception as e:
                errors.append(f"Job {job_id}: {e}")

        message = self._format_bulk_result(
            "Schedule enable completed.",
            updated=enabled,
            failed=len(errors),
            errors=errors,
        ).replace("Updated", "Enabled")
        if errors:
            Messagebox.show_warning(message, "Enable Complete")
        else:
            Messagebox.show_info(message, "Enable Complete")
        self._load_data()

    def _disable_schedule(self):
        """Disable selected schedules"""
        rows = self._get_selected_job_rows()
        if not rows:
            Messagebox.show_warning("Please select one or more schedules", "No Selection")
            return

        disabled = 0
        errors = []
        for row in rows:
            try:
                with Repository() as repo:
                    if repo.update_job(row['id'], enabled=False):
                        disabled += 1
                    else:
                        errors.append(f"Schedule not found for {row['switch_name']}")
                        continue
                if row['id'] in self.schedule_service.job_map:
                    self.schedule_service.pause_job(row['id'])
            except Exception as e:
                errors.append(f"{row['switch_name']}: {e}")

        message = self._format_bulk_result(
            "Schedule disable completed.",
            updated=disabled,
            failed=len(errors),
            errors=errors,
        ).replace("Updated", "Disabled")
        if errors:
            Messagebox.show_warning(message, "Disable Complete")
        else:
            Messagebox.show_info(message, "Disable Complete")
        self._load_data()
    
    def _start_now(self):
        """Manually trigger selected schedule(s) now - supports multiple selection"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select one or more schedules", "No Selection")
            return
        
        rows = self._get_selected_job_rows()
        jobs_to_run = [(row['id'], row['switch_name']) for row in rows]
        
        # Confirm action
        if len(jobs_to_run) == 1:
            message = f"Start backup now for {jobs_to_run[0][1]}?"
        else:
            switches_list = self._format_name_preview([name for _, name in jobs_to_run])
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
    
    def __init__(self, parent, schedule_service, job_id=None, callback=None, bulk=False):
        self.schedule_service = schedule_service
        self.job_id = job_id
        self.callback = callback
        self.bulk = bulk

        self.dialog = ttk.Toplevel(parent)
        if job_id:
            self.dialog.title("Edit Schedule")
        elif bulk:
            self.dialog.title("Bulk Add Schedules")
        else:
            self.dialog.title("Add Schedule")
        self.dialog.geometry("650x520" if bulk else "500x450")
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
        ttk.Label(frame, text="Switch:" if not self.bulk else "Switches:").grid(row=0, column=0, sticky=NW, pady=5)
        self.switch_var = ttk.StringVar()

        with Repository() as repo:
            switches = repo.list_switches()
            switch_names = [s.name for s in switches]

        if self.bulk:
            selector_frame = ttk.Frame(frame)
            selector_frame.grid(row=0, column=1, columnspan=2, sticky=NSEW, pady=5)
            self.switch_list = ttk.Treeview(
                selector_frame,
                columns=("Switch",),
                show="headings",
                height=8,
                selectmode="extended"
            )
            self.switch_list.heading("Switch", text="Switch")
            self.switch_list.column("Switch", width=300)
            for name in switch_names:
                self.switch_list.insert("", END, values=(name,))
            self.switch_list.pack(side=LEFT, fill=BOTH, expand=YES)
            switch_scrollbar = ttk.Scrollbar(selector_frame, orient=VERTICAL, command=self.switch_list.yview)
            self.switch_list.configure(yscrollcommand=switch_scrollbar.set)
            switch_scrollbar.pack(side=RIGHT, fill=Y)

            switch_button_frame = ttk.Frame(frame)
            switch_button_frame.grid(row=1, column=1, columnspan=2, sticky=W, pady=(0, 5))
            ttk.Button(
                switch_button_frame,
                text="Select All",
                command=lambda: self.switch_list.selection_set(self.switch_list.get_children()),
                bootstyle=SECONDARY,
            ).pack(side=LEFT, padx=5)
            ttk.Button(
                switch_button_frame,
                text="Clear",
                command=lambda: self.switch_list.selection_remove(self.switch_list.selection()),
                bootstyle=SECONDARY,
            ).pack(side=LEFT, padx=5)
            schedule_start_row = 2
        else:
            self.switch_combo = ttk.Combobox(frame, textvariable=self.switch_var, values=switch_names, state="readonly", width=35)
            self.switch_combo.grid(row=0, column=1, columnspan=2, pady=5, sticky=W)
            if switch_names:
                self.switch_combo.current(0)
            schedule_start_row = 1

        # Schedule Type
        ttk.Label(frame, text="Schedule Type:").grid(row=schedule_start_row, column=0, sticky=W, pady=10)
        self.schedule_type = ttk.StringVar(value="interval")

        type_frame = ttk.Frame(frame)
        type_frame.grid(row=schedule_start_row, column=1, columnspan=2, sticky=W, pady=10)
        
        ttk.Radiobutton(type_frame, text="Interval", variable=self.schedule_type, value="interval", command=self._toggle_schedule_type).pack(side=LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Daily", variable=self.schedule_type, value="daily", command=self._toggle_schedule_type).pack(side=LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Weekly", variable=self.schedule_type, value="weekly", command=self._toggle_schedule_type).pack(side=LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Monthly", variable=self.schedule_type, value="monthly", command=self._toggle_schedule_type).pack(side=LEFT, padx=5)
        
        # Interval Options (hidden/shown based on type)
        self.interval_frame = ttk.LabelFrame(frame, text="Interval Options", padding=10)
        self.interval_frame.grid(row=schedule_start_row + 1, column=0, columnspan=3, sticky=EW, pady=10)
        
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
        self.daily_frame.grid(row=schedule_start_row + 1, column=0, columnspan=3, sticky=EW, pady=10)
        
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
        self.weekly_frame.grid(row=schedule_start_row + 1, column=0, columnspan=3, sticky=EW, pady=10)
        
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
        self.monthly_frame.grid(row=schedule_start_row + 1, column=0, columnspan=3, sticky=EW, pady=10)
        
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
        btn_frame.grid(row=schedule_start_row + 2, column=0, columnspan=3, pady=20)
        
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
    
    def _get_selected_switch_names(self):
        if not self.bulk:
            return [self.switch_var.get()] if self.switch_var.get() else []
        names = []
        for item in self.switch_list.selection():
            values = self.switch_list.item(item)['values']
            if values:
                names.append(values[0])
        return names

    def _find_duplicate_job(self, jobs, switch_id, interval_minutes, schedule_hour, schedule_minute):
        for job in jobs:
            if (
                job.switch_id == switch_id
                and job.interval_minutes == interval_minutes
                and getattr(job, 'schedule_hour', 8) == schedule_hour
                and getattr(job, 'schedule_minute', 0) == schedule_minute
            ):
                return job
        return None

    def _save(self):
        """Save schedule"""
        switch_names = self._get_selected_switch_names()

        if not switch_names:
            Messagebox.show_error("Please select one or more switches", "Validation Error")
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
            jobs_to_schedule = []
            created = 0
            updated = 0
            skipped = 0
            errors = []

            with Repository() as repo:
                all_jobs = repo.list_jobs()
                switches = {switch.name: switch for switch in repo.list_switches()}

                if self.job_id:
                    switch = switches.get(switch_names[0])
                    if not switch:
                        Messagebox.show_error("Switch not found", "Error")
                        return
                    repo.update_job(self.job_id, interval_minutes=interval, schedule_hour=schedule_hour, schedule_minute=schedule_minute)
                    job_id = self.job_id
                    switch_id = switch.id
                    jobs_to_schedule.append((job_id, switch_id, interval, schedule_hour, schedule_minute, True))
                    updated = 1
                else:
                    duplicate_rows = []
                    for switch_name in switch_names:
                        switch = switches.get(switch_name)
                        if not switch:
                            errors.append(f"Switch not found: {switch_name}")
                            continue
                        duplicate = self._find_duplicate_job(
                            all_jobs,
                            switch.id,
                            interval,
                            schedule_hour,
                            schedule_minute,
                        )
                        if duplicate:
                            duplicate_rows.append((switch, duplicate))

                    duplicate_mode = "skip"
                    if duplicate_rows:
                        result = Messagebox.yesno(
                            f"Found {len(duplicate_rows)} duplicate schedule(s).\n\n"
                            "Choose Yes to update existing records.\n"
                            "Choose No to skip duplicates.",
                            "Duplicates Found"
                        )
                        duplicate_mode = "update" if result == "Yes" else "skip"

                    duplicate_by_switch = {switch.id: duplicate for switch, duplicate in duplicate_rows}
                    for switch_name in switch_names:
                        switch = switches.get(switch_name)
                        if not switch:
                            skipped += 1
                            continue
                        duplicate = duplicate_by_switch.get(switch.id)
                        if duplicate:
                            if duplicate_mode == "skip":
                                skipped += 1
                                continue
                            repo.update_job(
                                duplicate.id,
                                interval_minutes=interval,
                                enabled=True,
                                schedule_hour=schedule_hour,
                                schedule_minute=schedule_minute,
                            )
                            jobs_to_schedule.append((duplicate.id, switch.id, interval, schedule_hour, schedule_minute, True))
                            updated += 1
                        else:
                            job = repo.create_job(switch.id, interval, enabled=True)
                            job.schedule_hour = schedule_hour
                            job.schedule_minute = schedule_minute
                            jobs_to_schedule.append((job.id, switch.id, interval, schedule_hour, schedule_minute, True))
                            created += 1

            for job_id, switch_id, interval_minutes, job_hour, job_minute, enabled in jobs_to_schedule:
                if self.job_id:
                    self.schedule_service.remove_job(job_id)
                if enabled:
                    self.schedule_service.add_job(job_id, switch_id, interval_minutes, job_hour, job_minute)

            # Show summary
            type_desc = {
                "interval": f"Every {interval} minutes",
                "daily": f"Daily at {self.daily_hour.get()}:{int(self.daily_minute.get()):02d}",
                "weekly": f"Weekly on {self.weekly_day.get()} at {self.weekly_hour.get()}:{int(self.weekly_minute.get()):02d}",
                "monthly": f"Monthly on day {self.monthly_day.get()} at {self.monthly_hour.get()}:{int(self.monthly_minute.get()):02d}"
            }
            
            if self.bulk:
                message = (
                    f"Bulk schedule save complete.\n\n"
                    f"Created: {created}\n"
                    f"Updated: {updated}\n"
                    f"Skipped: {skipped}\n"
                    f"Failed: {len(errors)}"
                )
                if errors:
                    message += "\n\nErrors:\n" + "\n".join(errors[:10])
                Messagebox.show_info(message, "Success")
            else:
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
