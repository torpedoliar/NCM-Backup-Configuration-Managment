"""Retention service for cleaning up old backups"""
import logging
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import yaml

from app.data.repository import Repository

logger = logging.getLogger(__name__)


class RetentionService:
    """Manages backup retention and cleanup"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load retention configuration"""
        from app.config import get_config_path
        config_path = get_config_path()
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def start(self):
        """Start retention scheduler"""
        logger.info("Starting retention service")
        
        # Schedule daily cleanup at 2 AM
        cron_expr = self.config['scheduling']['retention_cron']
        trigger = CronTrigger.from_crontab(cron_expr)
        
        self.scheduler.add_job(
            func=self._cleanup_old_backups,
            trigger=trigger,
            id='retention_cleanup',
            replace_existing=True,
            name='Backup Retention Cleanup'
        )
        
        self.scheduler.start()
        logger.info("Retention service started")
    
    def stop(self):
        """Stop retention scheduler"""
        logger.info("Stopping retention service")
        self.scheduler.shutdown(wait=False)
    
    def cleanup_now(self):
        """Manually trigger cleanup"""
        logger.info("Manual retention cleanup triggered")
        self._cleanup_old_backups()
    
    def _cleanup_old_backups(self):
        """Clean up backups older than retention period"""
        try:
            retention_days = self.config['backup']['retention_days']
            min_keep = self.config['backup']['min_keep']
            
            logger.info(f"Starting backup cleanup: retention={retention_days} days, min_keep={min_keep}")
            
            with Repository() as repo:
                # Get all switches
                switches = repo.list_switches()
                
                total_deleted = 0
                
                for switch in switches:
                    # Get all backups for this switch
                    backups = repo.list_backups(switch_id=switch.id)
                    
                    if len(backups) <= min_keep:
                        logger.debug(f"Switch {switch.name}: {len(backups)} backups, skipping (below minimum)")
                        continue
                    
                    # Get backups older than retention period
                    old_backups = repo.get_backups_older_than(retention_days)
                    old_backups_for_switch = [b for b in old_backups if b.switch_id == switch.id]
                    
                    # Keep at least min_keep backups
                    if len(backups) - len(old_backups_for_switch) < min_keep:
                        keep_count = len(backups) - min_keep
                        old_backups_for_switch = old_backups_for_switch[:keep_count]
                    
                    # Delete old backups
                    for backup in old_backups_for_switch:
                        try:
                            # Delete file
                            if backup.file_path and Path(backup.file_path).exists():
                                Path(backup.file_path).unlink()
                                logger.debug(f"Deleted file: {backup.file_path}")
                            
                            # Delete DB record
                            repo.delete_backup(backup.id)
                            total_deleted += 1
                            
                        except Exception as e:
                            logger.error(f"Failed to delete backup {backup.id}: {e}")
                
                logger.info(f"Cleanup completed: {total_deleted} backups deleted")
                
        except Exception as e:
            logger.exception("Error during backup cleanup")
