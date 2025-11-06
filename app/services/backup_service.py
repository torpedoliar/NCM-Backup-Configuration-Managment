"""Backup service for executing and storing switch configurations"""
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Tuple
import yaml

from app.data.repository import Repository
from app.data.models import Switch, Backup
from app.services.crypto_service import CryptoService
from app.net.runner import BackupRunner
from app.services.diff_service import DiffService
from app.config.paths import get_base_dir

logger = logging.getLogger(__name__)


class BackupService:
    """Handles backup execution and storage"""
    
    def __init__(self, crypto_service: CryptoService):
        self.crypto = crypto_service
        self.runner = BackupRunner()
        self.config = self._load_config()
        self.diff = DiffService()
    
    def _load_config(self) -> dict:
        """Load backup configuration"""
        from app.config import get_config_path
        config_path = get_config_path()
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def execute_backup(self, switch_id: int, backup_type: str = 'manual', job_id: int = None) -> dict:
        """
        Execute backup for a switch
        
        Args:
            switch_id: ID of the switch to backup
            backup_type: Type of backup - 'automatic' or 'manual'
            
        Returns:
            Dict with backup result: {success, message, file_path, size_kb, backup_id}
        """
        # Load switch with credentials in a session context
        with Repository() as repo:
            switch = repo.get_switch(switch_id)
            if not switch:
                raise ValueError(f"Switch ID {switch_id} not found")
            
            # Get all needed data while in session
            switch_name = switch.name
            switch_protocol = switch.protocol
            switch_ip = switch.ip
            switch_port = switch.port
            credential_blob = switch.credential.enc_blob
        
        logger.info(f"Starting backup for switch: {switch_name}")
        
        try:
            # Decrypt credentials
            cred_data = self.crypto.decrypt_credential(credential_blob)
            username = cred_data['username']
            password = cred_data['password']
            enable_password = cred_data.get('enable_password', '')
            
            # Execute backup with retry
            success, config_text, message = self.runner.execute_backup(
                protocol=switch_protocol,
                host=switch_ip,
                port=switch_port,
                username=username,
                password=password,
                enable_password=enable_password
            )
            
            if not success:
                # Categorize error and get user-friendly message
                error_category, user_message = self._categorize_error(message)
                formatted_error = self._format_error_for_display(error_category, user_message)
                
                logger.error(f"Backup failed for {switch_name}")
                logger.error(f"  Category: {error_category}")
                logger.error(f"  Original Error: {message}")
                logger.error(f"  User Message: {user_message}")
                
                # Create failed backup record with current timestamp
                current_time = datetime.now()
                with Repository() as repo:
                    backup = repo.create_backup(
                        switch_id=switch_id,
                        file_path="",
                        content_hash="",
                        size_bytes=0,
                        success=False,
                        message=user_message,  # Store user-friendly message
                        backup_type=backup_type
                    )
                    # Update timestamp to local time
                    backup.taken_at = current_time
                    # Commit is handled by context manager
                    backup_id = backup.id
                
                return {
                    'success': False,
                    'message': user_message,  # Return user-friendly message
                    'error_category': error_category,
                    'file_path': '',
                    'size_kb': 0,
                    'backup_id': backup_id
                }
            
            # Calculate hash of current configuration
            content_hash = hashlib.sha256(config_text.encode('utf-8')).hexdigest()

            # Determine previous backup and whether configuration changed
            prev_backup = None
            changed = False
            try:
                with Repository() as repo:
                    prev_backup = repo.get_latest_backup(switch_id)
                    if prev_backup:
                        changed = (prev_backup.content_hash != content_hash)
            except Exception as e:
                logger.warning(f"Could not determine previous backup: {e}")

            # Save configuration to file, append suffix if changed
            name_suffix = " - update config" if changed else ""
            file_path = self._save_config_file(switch_name, config_text, name_suffix=name_suffix)

            # If there are changes, generate and save diff next to the backup file
            diff_stats = None
            if changed and prev_backup:
                try:
                    old_text = self.get_backup_content(prev_backup)
                    diff_text = self.diff.unified_diff(old_text, config_text, label1="Previous", label2="Current")
                    diff_stats = self.diff.get_diff_stats(old_text, config_text)
                    diff_file_path = Path(str(file_path).rsplit('.txt', 1)[0] + ".diff")
                    self.diff.export_diff(diff_text, str(diff_file_path))
                    logger.info(f"Diff saved to {diff_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to generate diff: {e}")

            # Compose user-facing message for history and console
            if changed:
                if diff_stats:
                    message = (
                        f"Perubahan konfigurasi terdeteksi: +{diff_stats['added_lines']}/-" 
                        f"{diff_stats['removed_lines']}/~{diff_stats['changed_lines']} baris"
                    )
                else:
                    message = "Perubahan konfigurasi terdeteksi"
            else:
                message = "Tidak ada perubahan konfigurasi"

            # Create backup record with current timestamp
            current_time = datetime.now()
            with Repository() as repo:
                backup = repo.create_backup(
                    switch_id=switch_id,
                    file_path=str(file_path),
                    content_hash=content_hash,
                    size_bytes=len(config_text),
                    success=True,
                    message=message,
                    backup_type=backup_type,
                    job_id=job_id
                )
                # Update timestamp to local time
                backup.taken_at = current_time
                # Commit is handled by context manager
                backup_id = backup.id

            logger.info(f"Backup completed for {switch_name}: {file_path}")

            return {
                'success': True,
                'message': message,
                'file_path': str(file_path),
                'size_kb': len(config_text) / 1024,
                'backup_id': backup_id
            }
            
        except Exception as e:
            logger.exception(f"Backup exception for {switch_name}")
            error_msg = str(e)
            
            # Categorize error and get user-friendly message
            error_category, user_message = self._categorize_error(error_msg)
            
            logger.error(f"  Exception Category: {error_category}")
            logger.error(f"  User Message: {user_message}")
            
            # Create failed backup record with current timestamp
            current_time = datetime.now()
            with Repository() as repo:
                backup = repo.create_backup(
                    switch_id=switch_id,
                    file_path="",
                    content_hash="",
                    size_bytes=0,
                    success=False,
                    message=user_message,  # Store user-friendly message
                    backup_type=backup_type,
                    job_id=job_id
                )
                # Update timestamp to local time
                backup.taken_at = current_time
                # Commit is handled by context manager
                backup_id = backup.id
            
            return {
                'success': False,
                'message': user_message,  # Return user-friendly message
                'error_category': error_category,
                'file_path': '',
                'size_kb': 0,
                'backup_id': backup_id
            }
    
    def _save_config_file(self, switch_name: str, config_text: str, name_suffix: str = "") -> Path:
        """
        Save configuration to file
        
        File structure: backups/<switch_name>/<YYYY-MM-DD>/<HHmmss>_running-config.txt
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        
        self.config = self._load_config()
        root_folder = Path(self.config['backup']['root_folder'])
        if not root_folder.is_absolute():
            root_folder = get_base_dir() / root_folder
        backup_dir = root_folder / switch_name / date_str
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"UNC_SHARE_AUTH_ERROR: {e}")
        
        file_name = f"{time_str}_running-config{name_suffix}.txt"
        file_path = backup_dir / file_name
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(config_text)
        
        logger.debug(f"Saved config to {file_path}")
        return file_path
    
    def _categorize_error(self, error_message: str) -> tuple:
        """Categorize error type and provide user-friendly message with suggestions
        
        Returns:
            tuple: (error_category, user_friendly_message)
        """
        error_lower = error_message.lower()
        
        # UNC share authentication/access errors
        if (
            'unc_share_auth_error' in error_lower
            or 'winerror 1326' in error_lower
            or ('the user name or password is incorrect' in error_lower and ('\\\\' in error_lower or 'unc' in error_lower))
        ):
            return (
                "SHARE_AUTH_ERROR",
                "❌ Share Authentication Failed: Akses ke network share ditolak. "
                "Suggestions: \n"
                "  • Jalankan layanan/Task Scheduler sebagai akun DOMAIN\\user yang punya akses share\n"
                "  • Buka Services → AlliedTelesisBackup → Log On → This account (isi user & password) lalu restart service\n"
                "  • Atau di Task Scheduler, set Run whether user is logged on or not dengan kredensial yang benar\n"
                "  • Verifikasi izin tulis ke folder UNC"
            )
        if 'access is denied' in error_lower and ('\\\\' in error_lower or 'unc' in error_lower):
            return (
                "SHARE_ACCESS_DENIED",
                "❌ Share Access Denied: Tidak memiliki permission ke network share. "
                "Suggestions: \n"
                "  • Pastikan akun layanan memiliki izin Read/Write pada folder share\n"
                "  • Jalankan layanan/Task Scheduler sebagai DOMAIN\\user dengan akses yang benar"
            )

        # Connection timeout errors
        if any(word in error_lower for word in ['timeout', 'timed out']):
            return (
                "CONNECTION_TIMEOUT",
                "❌ Connection Timeout: Switch tidak merespons dalam waktu yang ditentukan. "
                "Suggestions: \n"
                "  • Periksa switch dalam keadaan online (ping IP address)\n"
                "  • Periksa koneksi jaringan ke switch\n"
                "  • Switch mungkin sedang sibuk atau overloaded\n"
                "  • Coba tingkatkan timeout di settings"
            )
        
        # Connection refused
        if 'connection refused' in error_lower or 'no route' in error_lower:
            return (
                "CONNECTION_REFUSED",
                "❌ Connection Refused: Tidak dapat terhubung ke switch. "
                "Suggestions: \n"
                "  • Verifikasi IP address benar\n"
                "  • Pastikan SSH/Telnet service aktif di switch\n"
                "  • Periksa firewall tidak memblokir koneksi\n"
                "  • Verifikasi port number (SSH: 22, Telnet: 23)"
            )
        
        # Host unreachable
        if 'unreachable' in error_lower or 'no route to host' in error_lower:
            return (
                "HOST_UNREACHABLE",
                "❌ Host Unreachable: Switch tidak dapat dijangkau melalui jaringan. "
                "Suggestions: \n"
                "  • Periksa switch sudah terhubung ke network\n"
                "  • Verifikasi IP address dan subnet mask\n"
                "  • Periksa routing table\n"
                "  • Test koneksi dengan ping"
            )
        
        # Authentication errors
        if any(word in error_lower for word in ['authentication failed', 'login failed', 'incorrect', 'password', 'denied']):
            return (
                "AUTHENTICATION_ERROR",
                "❌ Authentication Failed: Username atau password salah. "
                "Suggestions: \n"
                "  • Verifikasi username dan password di Credentials tab\n"
                "  • Periksa CAPS LOCK tidak aktif\n"
                "  • Pastikan account tidak terkunci\n"
                "  • Coba test koneksi manual dengan SSH/Telnet client\n"
                "  • Periksa enable password jika diperlukan"
            )
        
        # Permission denied
        if 'permission' in error_lower:
            return (
                "PERMISSION_DENIED",
                "❌ Permission Denied: User tidak memiliki akses yang cukup. "
                "Suggestions: \n"
                "  • Pastikan user memiliki privilege level yang cukup\n"
                "  • Gunakan account dengan admin/enable access\n"
                "  • Periksa enable password sudah benar"
            )
        
        # Network errors
        if any(word in error_lower for word in ['network', 'socket', 'reset', 'broken pipe', 'connection reset']):
            return (
                "NETWORK_ERROR",
                "❌ Network Error: Koneksi terputus saat backup. "
                "Suggestions: \n"
                "  • Periksa stabilitas jaringan\n"
                "  • Switch mungkin restart atau disconnect\n"
                "  • Coba lagi beberapa saat\n"
                "  • Periksa kabel network atau wireless signal"
            )
        
        # SSH/Telnet protocol errors
        if 'ssh' in error_lower or 'key exchange' in error_lower:
            return (
                "SSH_PROTOCOL_ERROR",
                "❌ SSH Protocol Error: Masalah dengan protokol SSH. "
                "Suggestions: \n"
                "  • Verifikasi SSH version compatibility\n"
                "  • Coba gunakan Telnet jika SSH bermasalah\n"
                "  • Update SSH key algorithms di switch\n"
                "  • Periksa SSH configuration di switch"
            )
        
        if 'telnet' in error_lower:
            return (
                "TELNET_PROTOCOL_ERROR",
                "❌ Telnet Protocol Error: Masalah dengan protokol Telnet. "
                "Suggestions: \n"
                "  • Pastikan Telnet service aktif di switch\n"
                "  • Coba gunakan SSH untuk koneksi lebih secure\n"
                "  • Periksa Telnet configuration di switch"
            )
        
        # Command/Configuration errors
        if any(word in error_lower for word in ['command not found', 'invalid command', 'syntax error']):
            return (
                "COMMAND_ERROR",
                "❌ Command Error: Command tidak dikenali oleh switch. "
                "Suggestions: \n"
                "  • Command 'show running-config' mungkin berbeda di switch ini\n"
                "  • Verifikasi switch model dan OS version\n"
                "  • Periksa command syntax sesuai vendor\n"
                "  • Coba test command manual di switch CLI"
            )
        
        # Paging/output errors
        if any(word in error_lower for word in ['paging', 'more', '--more--', 'page']):
            return (
                "PAGING_ERROR",
                "❌ Paging Error: Gagal menonaktifkan pagination. "
                "Suggestions: \n"
                "  • Command 'terminal length 0' gagal\n"
                "  • Output config terpotong oleh pagination\n"
                "  • Coba disable paging manual di switch\n"
                "  • Periksa command untuk disable paging sesuai vendor"
            )
        
        # Encryption/Decryption errors
        if 'decrypt' in error_lower or 'encrypt' in error_lower or 'fernet' in error_lower:
            return (
                "ENCRYPTION_ERROR",
                "❌ Encryption Error: Gagal decrypt credentials. "
                "Suggestions: \n"
                "  • Master password mungkin berubah\n"
                "  • Credential mungkin corrupt\n"
                "  • Re-enter credential di Credentials tab\n"
                "  • Jika lupa master password, gunakan Factory Reset"
            )
        
        # Database errors
        if 'database' in error_lower or 'sqlite' in error_lower or 'locked' in error_lower:
            return (
                "DATABASE_ERROR",
                "❌ Database Error: Masalah dengan database. "
                "Suggestions: \n"
                "  • Database mungkin sedang diakses oleh proses lain\n"
                "  • Restart aplikasi\n"
                "  • Periksa file data/app.db tidak corrupt\n"
                "  • Pastikan ada write permission ke folder data/"
            )
        
        # File system errors
        if any(word in error_lower for word in ['permission denied', 'access denied', 'file', 'directory']):
            return (
                "FILESYSTEM_ERROR",
                "❌ Filesystem Error: Tidak dapat menulis file backup. "
                "Suggestions: \n"
                "  • Periksa write permission ke folder backups/\n"
                "  • Pastikan disk space cukup\n"
                "  • Folder backups/ mungkin read-only\n"
                "  • Run aplikasi dengan permission yang cukup"
            )
        
        # Generic error with original message
        return (
            "UNKNOWN_ERROR",
            f"❌ Unknown Error: {error_message}\n"
            "Suggestions: \n"
            "  • Periksa logs/app.log untuk detail error\n"
            "  • Coba lagi beberapa saat\n"
            "  • Jika masalah berlanjut, hubungi administrator\n"
            "  • Screenshot error message untuk troubleshooting"
        )
    
    def _format_error_for_display(self, error_category: str, user_message: str) -> str:
        """Format error message for display in GUI and logs"""
        return f"[{error_category}] {user_message}"
    
    def get_backup_content(self, backup: Backup) -> str:
        """Read backup file content"""
        try:
            with open(backup.file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read backup file {backup.file_path}: {e}")
            raise
