"""Enhanced Dashboard view with visual statistics"""
import logging
from datetime import datetime, timedelta
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import Canvas
import math

from app.data.repository import Repository

logger = logging.getLogger(__name__)


class DashboardView:
    """Dashboard view with backup statistics and charts"""
    
    def __init__(self, parent):
        self.parent = parent
        self.frame = ttk.Frame(parent, padding=10)
        self._create_ui()
        # Load statistics after UI is ready (non-blocking)
        self.frame.after(100, self._load_statistics)
        # Start auto-refresh
        self._start_auto_refresh()
    
    def _create_ui(self):
        """Create dashboard UI components"""
        # Title
        title_frame = ttk.Frame(self.frame)
        title_frame.pack(fill=X, pady=(0, 20))
        
        ttk.Label(
            title_frame,
            text="Dashboard Overview",
            font=("Segoe UI", 20, "bold"),
            bootstyle=PRIMARY
        ).pack(side=LEFT)
        
        ttk.Button(
            title_frame,
            text="🔄 Refresh",
            command=self._load_statistics,
            bootstyle=INFO
        ).pack(side=RIGHT)
        
        # Statistics Cards Row
        cards_frame = ttk.Frame(self.frame)
        cards_frame.pack(fill=X, pady=(0, 20))
        
        # Create 4 statistic cards
        self.total_switches_label = self._create_stat_card(
            cards_frame, "Total Switches", "0", SUCCESS, 0
        )
        self.total_backups_label = self._create_stat_card(
            cards_frame, "Total Backups", "0", INFO, 1
        )
        self.success_rate_label = self._create_stat_card(
            cards_frame, "Success Rate", "0%", PRIMARY, 2
        )
        self.last_backup_label = self._create_stat_card(
            cards_frame, "Last Backup", "Never", SECONDARY, 3
        )
        
        # Charts Row
        charts_frame = ttk.Frame(self.frame)
        charts_frame.pack(fill=BOTH, expand=YES)
        
        # Left side - Backup Status Chart
        left_panel = ttk.LabelFrame(
            charts_frame,
            text="Configuration Backup Summary",
            padding=20
        )
        left_panel.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 10))
        
        # Canvas for pie chart
        self.backup_chart_canvas = Canvas(
            left_panel,
            width=300,
            height=300,
            bg='white',
            highlightthickness=0
        )
        self.backup_chart_canvas.pack(pady=10)
        
        # Legend for backup chart
        legend_frame = ttk.Frame(left_panel)
        legend_frame.pack(pady=10)
        
        self._create_legend_item(legend_frame, "Backup Success", "#28a745", 0)
        self._create_legend_item(legend_frame, "Backup Failure", "#dc3545", 1)
        
        # Stats below chart
        self.success_count_label = ttk.Label(
            left_panel,
            text="Success: 0",
            font=("Segoe UI", 12),
            bootstyle=SUCCESS
        )
        self.success_count_label.pack()
        
        self.failure_count_label = ttk.Label(
            left_panel,
            text="Failure: 0",
            font=("Segoe UI", 12),
            bootstyle=DANGER
        )
        self.failure_count_label.pack()
        
        # Right side - Recent Activity & Schedule Status
        right_panel = ttk.Frame(charts_frame)
        right_panel.pack(side=RIGHT, fill=BOTH, expand=YES)
        
        # Schedule Status Chart
        schedule_panel = ttk.LabelFrame(
            right_panel,
            text="Schedule Status Summary",
            padding=20
        )
        schedule_panel.pack(fill=X, pady=(0, 10))
        
        self.schedule_chart_canvas = Canvas(
            schedule_panel,
            width=300,
            height=200,
            bg='white',
            highlightthickness=0
        )
        self.schedule_chart_canvas.pack(pady=10)
        
        # Legend for schedule chart
        schedule_legend_frame = ttk.Frame(schedule_panel)
        schedule_legend_frame.pack(pady=5)
        
        self._create_legend_item(schedule_legend_frame, "Enabled", "#007bff", 0)
        self._create_legend_item(schedule_legend_frame, "Disabled", "#6c757d", 1)
        
        self.enabled_schedules_label = ttk.Label(
            schedule_panel,
            text="Enabled: 0",
            font=("Segoe UI", 11),
            bootstyle=INFO
        )
        self.enabled_schedules_label.pack()
        
        self.disabled_schedules_label = ttk.Label(
            schedule_panel,
            text="Disabled: 0",
            font=("Segoe UI", 11),
            bootstyle=SECONDARY
        )
        self.disabled_schedules_label.pack()
        
        # Recent Activity
        activity_panel = ttk.LabelFrame(
            right_panel,
            text="Recent Backup Activity",
            padding=15
        )
        activity_panel.pack(fill=BOTH, expand=YES)
        
        # Scrollable text for recent activity
        activity_scroll = ttk.Scrollbar(activity_panel)
        activity_scroll.pack(side=RIGHT, fill=Y)
        
        self.activity_text = ttk.Text(
            activity_panel,
            height=10,
            width=40,
            yscrollcommand=activity_scroll.set,
            font=("Consolas", 9)
        )
        self.activity_text.pack(fill=BOTH, expand=YES)
        activity_scroll.config(command=self.activity_text.yview)
        
        # Configure text tags for colors
        self.activity_text.tag_config("success", foreground="#28a745")
        self.activity_text.tag_config("failure", foreground="#dc3545")
        self.activity_text.tag_config("time", foreground="#6c757d")
    
    def _create_stat_card(self, parent, title, value, bootstyle, column):
        """Create a statistic card"""
        card = ttk.Frame(parent, bootstyle=bootstyle)
        card.grid(row=0, column=column, padx=10, sticky='ew')
        parent.columnconfigure(column, weight=1)
        
        # Card content
        card_inner = ttk.Frame(card, bootstyle=bootstyle)
        card_inner.pack(fill=BOTH, expand=YES, padx=2, pady=2)
        
        ttk.Label(
            card_inner,
            text=title,
            font=("Segoe UI", 11),
            bootstyle=f"{bootstyle}-inverse"
        ).pack(pady=(10, 5))
        
        value_label = ttk.Label(
            card_inner,
            text=value,
            font=("Segoe UI", 24, "bold"),
            bootstyle=f"{bootstyle}-inverse"
        )
        value_label.pack(pady=(0, 10))
        
        return value_label
    
    def _create_legend_item(self, parent, text, color, row):
        """Create a legend item"""
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky=W, pady=2, padx=20)
        
        # Color box
        canvas = Canvas(frame, width=20, height=20, bg='white', highlightthickness=0)
        canvas.pack(side=LEFT, padx=(0, 10))
        canvas.create_rectangle(2, 2, 18, 18, fill=color, outline=color)
        
        # Label
        ttk.Label(frame, text=text, font=("Segoe UI", 10)).pack(side=LEFT)
    
    def _draw_pie_chart(self, canvas, success, failure, colors=("#28a745", "#dc3545")):
        """Draw a pie chart on canvas"""
        canvas.delete("all")
        
        total = success + failure
        if total == 0:
            # Draw empty circle
            canvas.create_oval(50, 50, 250, 250, fill="#e9ecef", outline="#dee2e6", width=2)
            canvas.create_text(150, 150, text="No Data", font=("Segoe UI", 14), fill="#6c757d")
            return
        
        # Calculate angles
        success_angle = (success / total) * 360
        
        # Center and radius
        cx, cy = 150, 150
        radius = 100
        
        # Draw success slice
        if success > 0:
            self._draw_pie_slice(canvas, cx, cy, radius, 90, 90 - success_angle, colors[0])
        
        # Draw failure slice
        if failure > 0:
            self._draw_pie_slice(canvas, cx, cy, radius, 90 - success_angle, 90 - success_angle - (360 - success_angle), colors[1])
        
        # Draw center circle for donut effect
        canvas.create_oval(100, 100, 200, 200, fill="white", outline="white")
        
        # Draw total in center
        canvas.create_text(
            150, 150,
            text=str(total),
            font=("Segoe UI", 32, "bold"),
            fill="#212529"
        )
    
    def _draw_pie_slice(self, canvas, cx, cy, radius, start_angle, end_angle, color):
        """Draw a pie slice"""
        # Calculate points for the slice
        points = [cx, cy]
        
        # Number of segments for smooth arc
        segments = max(2, int(abs(end_angle - start_angle)))
        
        for i in range(segments + 1):
            angle = math.radians(start_angle + (end_angle - start_angle) * i / segments)
            x = cx + radius * math.cos(angle)
            y = cy - radius * math.sin(angle)
            points.extend([x, y])
        
        # Draw the slice
        canvas.create_polygon(points, fill=color, outline=color, smooth=True)
    
    def _load_statistics(self):
        """Load and display statistics"""
        try:
            with Repository() as repo:
                # Get switches
                switches = repo.list_switches()
                total_switches = len(switches)
                
                # Get backups from last 30 days
                since_date = datetime.now() - timedelta(days=30)
                all_backups = repo.list_backups()
                recent_backups = [b for b in all_backups if b.taken_at >= since_date]
                
                total_backups = len(recent_backups)
                success_backups = len([b for b in recent_backups if b.success])
                failure_backups = len([b for b in recent_backups if not b.success])
                
                # Calculate success rate
                success_rate = (success_backups / total_backups * 100) if total_backups > 0 else 0
                
                # Get last backup time
                if all_backups:
                    last_backup = max(all_backups, key=lambda b: b.taken_at)
                    last_backup_text = last_backup.taken_at.strftime("%Y-%m-%d %H:%M")
                else:
                    last_backup_text = "Never"
                
                # Get schedules
                jobs = repo.list_jobs()
                enabled_schedules = len([j for j in jobs if j.enabled])
                disabled_schedules = len([j for j in jobs if not j.enabled])
                
                # Update stat cards
                self.total_switches_label.config(text=str(total_switches))
                self.total_backups_label.config(text=str(total_backups))
                self.success_rate_label.config(text=f"{success_rate:.1f}%")
                self.last_backup_label.config(text=last_backup_text)
                
                # Update backup chart
                self._draw_pie_chart(
                    self.backup_chart_canvas,
                    success_backups,
                    failure_backups
                )
                
                self.success_count_label.config(text=f"Success: {success_backups}")
                self.failure_count_label.config(text=f"Failure: {failure_backups}")
                
                # Update schedule chart
                self._draw_pie_chart(
                    self.schedule_chart_canvas,
                    enabled_schedules,
                    disabled_schedules,
                    colors=("#007bff", "#6c757d")
                )
                
                self.enabled_schedules_label.config(text=f"Enabled: {enabled_schedules}")
                self.disabled_schedules_label.config(text=f"Disabled: {disabled_schedules}")
                
                # Update recent activity
                self.activity_text.config(state="normal")
                self.activity_text.delete("1.0", END)
                
                # Show last 20 backups
                recent_activity = sorted(all_backups, key=lambda b: b.taken_at, reverse=True)[:20]
                
                for backup in recent_activity:
                    time_str = backup.taken_at.strftime("%Y-%m-%d %H:%M:%S")
                    status = "✓ SUCCESS" if backup.success else "✗ FAILED"
                    tag = "success" if backup.success else "failure"
                    
                    self.activity_text.insert(END, f"{time_str}", "time")
                    self.activity_text.insert(END, f" - {status}\n", tag)
                
                if not recent_activity:
                    self.activity_text.insert(END, "No backup activity yet\n")
                
                self.activity_text.config(state="disabled")
                
        except Exception as e:
            logger.exception("Failed to load dashboard statistics")
            self.total_switches_label.config(text="Error")
            self.total_backups_label.config(text="Error")
            self.success_rate_label.config(text="Error")
            self.last_backup_label.config(text="Error")
    
    def _start_auto_refresh(self):
        """Start auto-refresh timer"""
        self._auto_refresh()
    
    def _auto_refresh(self):
        """Auto-refresh dashboard statistics every 30 seconds"""
        try:
            self._load_statistics()
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
        
        # Schedule next refresh in 30 seconds
        self.frame.after(30000, self._auto_refresh)
    
    def refresh(self):
        """Refresh dashboard data"""
        self._load_statistics()
