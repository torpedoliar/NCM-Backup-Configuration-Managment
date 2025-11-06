"""Scheduling service for automated backups"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import threading
import time
import os
from pathlib import Path

from app.data.repository import Repository
from app.services.crypto_service import CryptoService
from app.services.backup_service import BackupService
from app.config.paths import get_base_dir

logger = logging.getLogger(__name__)


class ScheduleService:
    """Manages scheduled backup jobs"""
    
    def __init__(self, crypto_service: CryptoService):
        self.crypto = crypto_service
        self.backup_service = BackupService(crypto_service)
        self.console = None  # Reference to app window for console logging
        # Configure scheduler with timezone awareness
        self.scheduler = BackgroundScheduler(
            job_defaults={
                'coalesce': False,
                'max_instances': 3
            }
        )
        self.job_map = {}  # Maps job_id to APScheduler job_id
        self.job_interval_map = {}  # Track interval minutes per job_id
        self.job_time_map = {}      # Track (hour, minute) per job_id
        self._sync_thread = None
        self._stop_sync = False
        # Single-instance scheduler lock
        self._lock_file = get_base_dir() / "data" / "scheduler.lock"
        self._lock_acquired = False
    
    def set_console(self, app_window):
        """Set reference to app window for console logging"""
        self.console = app_window
        if self.console:
            self.console.write_console("Schedule service connected to console")
    
    def start(self):
        """Start the scheduler and register existing jobs"""
        logger.info("="*70)
        logger.info("STARTING SCHEDULE SERVICE")
        logger.info("="*70)
        
        # Try to acquire single-instance lock
        if not self._acquire_lock():
            logger.info("Another scheduler instance is active (lock present). This instance will not start scheduler.")
            return
        
        self.scheduler.start()
        logger.info("✓ APScheduler engine started")
        
        # Load and register all enabled jobs from database
        with Repository() as repo:
            jobs = repo.list_jobs()
            total_jobs = len(jobs)
            enabled_jobs = [job for job in jobs if job.enabled]
            active_count = len(enabled_jobs)
            
            logger.info(f"Database query: Found {total_jobs} total jobs")
            logger.info(f"  • Enabled: {active_count}")
            logger.info(f"  • Disabled: {total_jobs - active_count}")
            
            if active_count == 0:
                logger.warning("⚠️  NO ENABLED SCHEDULES FOUND!")
                logger.warning("  → Schedules will NOT run automatically")
                logger.warning("  → Enable schedules in GUI Schedules tab")
            else:
                logger.info(f"Loading {active_count} enabled schedule(s)...")
                
                for job in enabled_jobs:
                    switch_name = job.switch.name if job.switch else "Unknown"
                    schedule_hour = getattr(job, 'schedule_hour', 8)
                    schedule_minute = getattr(job, 'schedule_minute', 0)
                    
                    logger.info(f"  [Job {job.id}] {switch_name}")
                    logger.info(f"    • Interval: {job.interval_minutes} minutes")
                    logger.info(f"    • Time: {schedule_hour:02d}:{schedule_minute:02d}")
                    logger.info(f"    • Last Run: {job.last_ran_at if job.last_ran_at else 'Never'}")
                    
                    try:
                        self.add_job(job.id, job.switch_id, job.interval_minutes, schedule_hour, schedule_minute)
                        logger.info(f"    • Status: ✅ Added to scheduler")
                    except Exception as e:
                        logger.error(f"    • Status: ❌ Failed to add: {e}")
                
                logger.info(f"✓ {active_count} schedule(s) registered successfully")
        
        logger.info("="*70)
        logger.info(f"SCHEDULE SERVICE READY - {active_count} active job(s)")
        logger.info("="*70)
        
        # Start background sync watcher to reflect DB changes dynamically
        if not self._sync_thread or not self._sync_thread.is_alive():
            self._stop_sync = False
            self._sync_thread = threading.Thread(target=self._sync_watcher, daemon=True)
            self._sync_thread.start()
            logger.info("Schedule DB sync watcher started (every 30s)")
    
    def stop(self):
        """Stop scheduler"""
        logger.info("Stopping schedule service")
        self._stop_sync = True
        try:
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=1)
        except Exception:
            pass
        self.scheduler.shutdown(wait=False)
        self._release_lock()
    
    def add_job(self, job_id: int, switch_id: int, interval_minutes: int, schedule_hour: int = 8, schedule_minute: int = 0):
        """Add a new scheduled job"""
        try:
            # Remove existing job if present (for update case)
            if job_id in self.job_map:
                logger.info(f"Job {job_id} already exists, removing before re-adding")
                self.remove_job(job_id)
            
            self._register_job(job_id, switch_id, interval_minutes, schedule_hour, schedule_minute)
            
            # Verify job was added
            aps_job_id = self.job_map.get(job_id)
            if aps_job_id:
                job = self.scheduler.get_job(aps_job_id)
                if job:
                    next_run = getattr(job, 'next_run_time', 'calculating...')
                    logger.info(f"✓ Added schedule for job {job_id}: every {interval_minutes} minutes, next run at {next_run}")
                else:
                    logger.error(f"✗ Job {job_id} registered but not found in scheduler!")
            else:
                logger.error(f"✗ Job {job_id} not in job_map after registration!")
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {e}")
            raise
    
    def remove_job(self, job_id: int):
        """Remove a scheduled job"""
        try:
            if job_id in self.job_map:
                apscheduler_job_id = self.job_map[job_id]
                self.scheduler.remove_job(apscheduler_job_id)
                del self.job_map[job_id]
                self.job_interval_map.pop(job_id, None)
                self.job_time_map.pop(job_id, None)
                logger.info(f"Removed schedule for job {job_id}")
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            raise
    
    def pause_job(self, job_id: int):
        """Pause a scheduled job"""
        try:
            if job_id in self.job_map:
                apscheduler_job_id = self.job_map[job_id]
                self.scheduler.pause_job(apscheduler_job_id)
                logger.info(f"Paused job {job_id}")
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            raise
    
    def resume_job(self, job_id: int):
        """Resume a paused job"""
        try:
            if job_id in self.job_map:
                apscheduler_job_id = self.job_map[job_id]
                self.scheduler.resume_job(apscheduler_job_id)
                logger.info(f"Resumed job {job_id}")
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            raise
    
    def get_job_status(self, job_id: int) -> dict:
        """Get status of a specific job"""
        if job_id not in self.job_map:
            return {'status': 'not_found', 'message': 'Job not in map'}
        
        aps_job_id = self.job_map[job_id]
        job = self.scheduler.get_job(aps_job_id)
        
        if not job:
            return {'status': 'not_in_scheduler', 'message': 'Job not found in scheduler'}
        
        return {
            'status': 'active',
            'next_run': job.next_run_time,
            'trigger': str(job.trigger)
        }
    
    def _register_job(self, job_id: int, switch_id: int, interval_minutes: int, schedule_hour: int = 8, schedule_minute: int = 0):
        """Register job with APScheduler"""
        apscheduler_job_id = f"backup_job_{job_id}"
        trigger = self._build_trigger(interval_minutes, schedule_hour, schedule_minute)
        if isinstance(trigger, IntervalTrigger):
            logger.info(f"Scheduling interval job {job_id} every {interval_minutes} minutes")
        else:
            logger.info(f"Scheduling cron job {job_id}")

        self.scheduler.add_job(
            func=self._execute_scheduled_backup,
            trigger=trigger,
            id=apscheduler_job_id,
            args=[job_id, switch_id],
            replace_existing=True,
            name=f"Backup Job {job_id}"
        )

        self.job_map[job_id] = apscheduler_job_id
        self.job_interval_map[job_id] = interval_minutes
        self.job_time_map[job_id] = (schedule_hour, schedule_minute)

        registered_job = self.scheduler.get_job(apscheduler_job_id)
        if registered_job:
            next_run = getattr(registered_job, 'next_run_time', 'calculating...')
            logger.info(f"✓ Registered job {job_id}: trigger={type(trigger).__name__}, next_run={next_run}")
        else:
            logger.error(f"✗ Failed to register job {job_id} in scheduler")

    def _build_trigger(self, interval_minutes: int, schedule_hour: int = 8, schedule_minute: int = 0):
        from apscheduler.triggers.cron import CronTrigger
        if interval_minutes == 1440:  # Daily
            return CronTrigger(hour=schedule_hour, minute=schedule_minute)
        elif interval_minutes == 10080:  # Weekly (Monday)
            return CronTrigger(day_of_week='mon', hour=schedule_hour, minute=schedule_minute)
        elif interval_minutes == 43200:  # Monthly (1st)
            return CronTrigger(day=1, hour=schedule_hour, minute=schedule_minute)
        else:
            return IntervalTrigger(minutes=interval_minutes)

    def _sync_watcher(self, interval_sec: int = 30):
        while not self._stop_sync:
            try:
                self._sync_once()
            except Exception as e:
                logger.error(f"Schedule sync failed: {e}")
            # Heartbeat: update lock mtime if we hold the lock
            try:
                if self._lock_acquired and self._lock_file.exists():
                    os.utime(self._lock_file, None)
            except Exception:
                pass
            time.sleep(interval_sec)

    def _acquire_lock(self) -> bool:
        """Acquire single-instance lock by creating lock file exclusively"""
        try:
            lock_dir: Path = self._lock_file.parent
            lock_dir.mkdir(parents=True, exist_ok=True)
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            fd = os.open(self._lock_file, flags)
            with os.fdopen(fd, 'w') as f:
                f.write(f"{os.getpid()} {int(time.time())}\n")
            self._lock_acquired = True
            return True
        except FileExistsError:
            # Possible stale lock - if older than 3 minutes, remove and retry once
            try:
                if self._lock_file.exists():
                    mtime = self._lock_file.stat().st_mtime
                    age = time.time() - mtime
                    if age > 180:  # 3 minutes
                        logger.warning("Detected stale scheduler.lock (older than 3 minutes). Removing...")
                        self._lock_file.unlink()
                        # Retry acquire once
                        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
                        fd = os.open(self._lock_file, flags)
                        with os.fdopen(fd, 'w') as f:
                            f.write(f"{os.getpid()} {int(time.time())}\n")
                        self._lock_acquired = True
                        return True
            except Exception as stale_err:
                logger.warning(f"Failed to recover stale lock: {stale_err}")
            return False
        except Exception as e:
            logger.warning(f"Failed to create scheduler lock: {e}")
            return False

    def _release_lock(self):
        """Release lock if held by this instance"""
        if self._lock_acquired:
            try:
                if self._lock_file.exists():
                    self._lock_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove scheduler lock: {e}")
            self._lock_acquired = False

    def _sync_once(self):
        with Repository() as repo:
            jobs = repo.list_jobs()
            db_enabled_ids = {job.id for job in jobs if job.enabled}
            # Remove jobs that are disabled or deleted
            for jid in list(self.job_map.keys()):
                if jid not in db_enabled_ids:
                    try:
                        self.remove_job(jid)
                    except Exception as e:
                        logger.warning(f"Failed to remove job {jid} during sync: {e}")
            # Ensure enabled jobs exist and match DB settings
            for job in jobs:
                schedule_hour = getattr(job, 'schedule_hour', 8)
                schedule_minute = getattr(job, 'schedule_minute', 0)
                if job.enabled:
                    prev_interval = self.job_interval_map.get(job.id)
                    prev_time = self.job_time_map.get(job.id)
                    if job.id not in self.job_map:
                        self.add_job(job.id, job.switch_id, job.interval_minutes, schedule_hour, schedule_minute)
                    elif prev_interval != job.interval_minutes or prev_time != (schedule_hour, schedule_minute):
                        try:
                            aps_job_id = self.job_map[job.id]
                            new_trigger = self._build_trigger(job.interval_minutes, schedule_hour, schedule_minute)
                            self.scheduler.reschedule_job(aps_job_id, trigger=new_trigger)
                            self.job_interval_map[job.id] = job.interval_minutes
                            self.job_time_map[job.id] = (schedule_hour, schedule_minute)
                            logger.info(f"Rescheduled job {job.id} to new settings (interval={job.interval_minutes} min)")
                        except Exception as e:
                            logger.warning(f"Reschedule failed for job {job.id}: {e}; attempting re-add")
                            try:
                                self.remove_job(job.id)
                            except Exception:
                                pass
                            self.add_job(job.id, job.switch_id, job.interval_minutes, schedule_hour, schedule_minute)
    
    def _catch_up_missed_schedules(self):
        """Run all enabled schedules immediately on app startup"""
        logger.info("Auto-starting all enabled schedules...")
        
        try:
            with Repository() as repo:
                jobs = repo.list_jobs(enabled_only=True)
                started = 0
                current_time = datetime.now()
                
                for job in jobs:
                    # Check if this is a new schedule (never run before)
                    if not job.last_ran_at:
                        msg = f"[AUTO-START] {job.switch.name} - Starting first backup now"
                        logger.info(f"[AUTO-START] Job {job.id} (Switch: {job.switch.name}) - new schedule, running first backup")
                        status = "AUTO-START"
                    else:
                        # Existing schedule - run immediately on app startup
                        msg = f"[AUTO-START] {job.switch.name} - Running backup on app startup"
                        logger.info(f"[AUTO-START] Job {job.id} (Switch: {job.switch.name}) - running on app startup")
                        status = "AUTO-START"
                    
                    if self.console:
                        self.console.write_console(msg, status)
                    
                    # Run the backup immediately
                    import threading
                    thread = threading.Thread(
                        target=self._execute_scheduled_backup,
                        args=(job.id, job.switch_id),
                        daemon=True
                    )
                    thread.start()
                    started += 1
                
                if started > 0:
                    logger.info(f"[AUTO-START] Started {started} backup(s)")
                else:
                    logger.info("[AUTO-START] All schedules are current")
                    
        except Exception as e:
            logger.exception(f"[CATCH-UP] Error checking for missed schedules: {e}")
    
    def get_next_run_time(self, job_id: int):
        """Get the actual next run time from APScheduler"""
        try:
            if job_id in self.job_map:
                aps_job_id = self.job_map[job_id]
                job = self.scheduler.get_job(aps_job_id)
                if job and job.next_run_time:
                    # Convert timezone-aware datetime to naive local time
                    next_run = job.next_run_time
                    if next_run.tzinfo is not None:
                        # Convert to local time and remove timezone info
                        next_run = next_run.astimezone().replace(tzinfo=None)
                    return next_run
        except Exception as e:
            logger.error(f"Error getting next run time for job {job_id}: {e}")
        return None
    
    def _execute_scheduled_backup(self, job_id: int, switch_id: int):
        """Execute backup for scheduled job"""
        execution_start = datetime.now()
        try:
            # Get switch name for console logging
            switch_name = "Unknown"
            job_interval = 0
            with Repository() as repo:
                job = repo.get_job(job_id)
                if job and job.switch:
                    switch_name = job.switch.name
                    job_interval = job.interval_minutes
            
            logger.info(f"[BACKGROUND-JOB] Starting scheduled backup")
            logger.info(f"  Job ID: {job_id} | Switch: {switch_name} | Type: Automatic")
            logger.info(f"  Execution Time: {execution_start.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if self.console:
                self.console.write_console(f"[BACKUP] {switch_name} - Starting scheduled backup...", "BACKUP")
            
            # Execute backup with automatic type and job_id
            result = self.backup_service.execute_backup(switch_id, backup_type='automatic', job_id=job_id)
            
            # Update job last_ran_at with local time (not UTC)
            execution_end = datetime.now()
            with Repository() as repo:
                repo.update_job(job_id, last_ran_at=execution_start)
            
            if result['success']:
                duration = (execution_end - execution_start).total_seconds()
                logger.info(f"[BACKGROUND-JOB] ✅ Backup completed successfully")
                logger.info(f"  Switch: {switch_name} | Size: {result['size_kb']:.1f} KB | Duration: {duration:.1f}s")
                logger.info(f"  Backup ID: {result.get('backup_id', 'N/A')} | File: {result.get('file_path', 'N/A')}")
                logger.info(f"  Next scheduled run: Based on interval {job_interval} minutes")
                if self.console:
                    self.console.write_console(f"[SUCCESS] {switch_name} - Backup completed ({result['size_kb']:.1f} KB)", "SUCCESS")
            else:
                error_category = result.get('error_category', 'UNKNOWN_ERROR')
                error_message = result['message']
                
                logger.warning(f"[BACKGROUND-JOB] ❌ Backup failed")
                logger.warning(f"  Switch: {switch_name}")
                logger.warning(f"  Error Category: {error_category}")
                logger.warning(f"  Error Message: {error_message}")
                logger.warning(f"  Job will retry on next scheduled time")
                
                # Show first line of error message in console (user-friendly)
                error_summary = error_message.split('\\n')[0] if '\\n' in error_message else error_message
                if self.console:
                    self.console.write_console(f"[FAILED] {switch_name} - {error_summary}", "ERROR")
                
        except Exception as e:
            logger.exception(f"[SCHEDULE] Error in scheduled backup for job {job_id}")
            if self.console:
                self.console.write_console(f"[ERROR] Backup error: {str(e)}", "ERROR")
