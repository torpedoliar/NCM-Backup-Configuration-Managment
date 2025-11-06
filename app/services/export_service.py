"""Export service for saving configs and diffs"""
import logging
import shutil
from pathlib import Path
from app.data.models import Backup

logger = logging.getLogger(__name__)


class ExportService:
    """Handles exporting configurations and diffs"""
    
    def export_config(self, backup: Backup, dest_path: str) -> bool:
        """
        Export backup configuration to file
        
        Args:
            backup: Backup model
            dest_path: Destination file path
            
        Returns:
            True if successful
        """
        try:
            if not backup.file_path or not Path(backup.file_path).exists():
                logger.error(f"Backup file not found: {backup.file_path}")
                return False
            
            shutil.copy2(backup.file_path, dest_path)
            logger.info(f"Config exported to {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            return False
    
    def export_diff(self, diff_text: str, dest_path: str) -> bool:
        """
        Export diff to file
        
        Args:
            diff_text: Diff content
            dest_path: Destination file path
            
        Returns:
            True if successful
        """
        try:
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(diff_text)
            logger.info(f"Diff exported to {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export diff: {e}")
            return False
    
    def open_containing_folder(self, file_path: str) -> bool:
        """
        Open file's containing folder in explorer
        
        Args:
            file_path: Path to file
            
        Returns:
            True if successful
        """
        try:
            import subprocess
            folder = Path(file_path).parent
            
            if not folder.exists():
                logger.error(f"Folder not found: {folder}")
                return False
            
            # Windows explorer
            subprocess.Popen(f'explorer "{folder}"')
            logger.info(f"Opened folder: {folder}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")
            return False
