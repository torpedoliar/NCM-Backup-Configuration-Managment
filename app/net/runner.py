"""Common backup execution logic with retry and normalization"""
import logging
import time
import asyncio
from typing import Dict, Tuple
from pathlib import Path
import yaml

from app.net.ssh_client import SSHClient
from app.net.telnet_client import TelnetClient
from app.net.web_smart_client import WebSmartClient
from app.net.traditional_web_smart_client import TraditionalWebSmartClient

logger = logging.getLogger(__name__)


class BackupRunner:
    """Unified interface for executing backups via SSH, Telnet, or HTTP (WebSmart)"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load network configuration"""
        from app.config import get_config_path
        config_path = get_config_path()
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def execute_backup(self, protocol: str, host: str, port: int,
                      username: str, password: str, enable_password: str = "") -> Tuple[bool, str, str]:
        """
        Execute backup with retry logic
        
        Returns:
            Tuple of (success: bool, config_text: str, message: str)
        """
        max_retries = self.config['network']['max_retries']
        retry_delay = self.config['network']['retry_delay']
        backoff = self.config['network']['backoff_multiplier']
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = retry_delay * (backoff ** attempt)
                    logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {wait_time}s")
                    time.sleep(wait_time)
                
                if protocol.lower() == 'ssh':
                    config_text = self._execute_ssh(host, port, username, password, enable_password)
                elif protocol.lower() == 'telnet':
                    config_text = self._execute_telnet(host, port, username, password, enable_password)
                elif protocol.lower() in ['http', 'https', 'websmart']:
                    # Traditional WebSmart (FS750, GS950 old models) - NO V2 attempt
                    config_text = self._execute_http(host, port, username, password, force_v2=False)
                elif protocol.lower() == 'websmart-v2':
                    # WebSmart V2 (GS950/52PS V2) - ONLY V2 authentication
                    config_text = self._execute_http(host, port, username, password, force_v2=True)
                else:
                    return False, "", f"Unsupported protocol: {protocol}"
                
                # Normalize output
                config_text = self._normalize_output(config_text)
                
                if len(config_text) < 100:
                    raise ValueError("Retrieved configuration too short, likely incomplete")
                
                return True, config_text, "Backup completed successfully"
                
            except Exception as e:
                logger.error(f"Backup attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return False, "", f"Backup failed after {max_retries} attempts: {str(e)}"
        
        return False, "", "Backup failed"
    
    def _execute_ssh(self, host: str, port: int, username: str,
                     password: str, enable_password: str) -> str:
        """Execute backup via SSH"""
        client = None
        try:
            timeout = self.config['network']['connect_timeout']
            client = SSHClient(host, port, username, password, enable_password, timeout)
            
            # Connect
            client.connect()
            
            # Enter enable mode
            prompts = self.config['network']['prompts']
            client.enter_enable_mode(prompts)
            
            # Disable paging
            paging_cmds = self.config['network']['paging_disable_commands']
            client.disable_paging(paging_cmds)
            
            # Get running config
            paging_indicators = self.config['network']['paging_indicators']
            config_text = client.get_running_config(paging_indicators)
            
            return config_text
            
        finally:
            if client:
                client.disconnect()
    
    def _execute_telnet(self, host: str, port: int, username: str,
                       password: str, enable_password: str) -> str:
        """Execute backup via Telnet (runs async in sync context)"""
        return asyncio.run(self._execute_telnet_async(
            host, port, username, password, enable_password
        ))
    
    async def _execute_telnet_async(self, host: str, port: int, username: str,
                                    password: str, enable_password: str) -> str:
        """Async Telnet backup execution"""
        client = None
        try:
            timeout = self.config['network']['connect_timeout']
            client = TelnetClient(host, port, username, password, enable_password, timeout)
            
            # Connect
            await client.connect()
            
            # Enter enable mode
            prompts = self.config['network']['prompts']
            await client.enter_enable_mode(prompts)
            
            # Disable paging
            paging_cmds = self.config['network']['paging_disable_commands']
            await client.disable_paging(paging_cmds)
            
            # Get running config
            paging_indicators = self.config['network']['paging_indicators']
            config_text = await client.get_running_config(paging_indicators)
            
            return config_text
            
        finally:
            if client:
                await client.disconnect()

    def _execute_http(self, host: str, port: int, username: str, password: str, force_v2: bool = False) -> str:
        """Execute backup via HTTP/WebSmart"""
        client = None
        try:
            timeout = self.config['network']['connect_timeout']
            
            if force_v2:
                # WebSmart V2 - Use V2-only client
                client = WebSmartClient(host, port, username, password, timeout, force_v2_only=True)
            else:
                # Traditional WebSmart - Use proven backup code
                client = TraditionalWebSmartClient(host, port, username, password, timeout)
            
            # Connect/Login
            client.connect()
            
            # Get config
            config_text = client.get_running_config()
            
            return config_text
            
        finally:
            if client:
                client.disconnect()
    
    def _normalize_output(self, text: str) -> str:
        """Normalize line endings and whitespace"""
        # Convert all line endings to \n
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove trailing whitespace from each line
        lines = [line.rstrip() for line in text.split('\n')]
        
        # Remove empty lines at start and end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)
