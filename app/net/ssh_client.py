"""SSH client for switch connections"""
import logging
import time
import paramiko
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class SSHClient:
    """SSH connection handler for network devices"""
    
    def __init__(self, host: str, port: int, username: str, password: str,
                 enable_password: str = "", timeout: int = 15):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
        self.shell = None
    
    def connect(self) -> bool:
        """Establish SSH connection"""
        try:
            logger.info(f"Connecting to {self.host}:{self.port} via SSH")
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False
            )
            
            self.shell = self.client.invoke_shell()
            time.sleep(1)  # Wait for shell to initialize
            
            # Clear initial banner
            if self.shell.recv_ready():
                self.shell.recv(65535)
            
            logger.info(f"Connected to {self.host}")
            return True
            
        except Exception as e:
            logger.error(f"SSH connection failed to {self.host}: {e}")
            raise ConnectionError(f"SSH connection failed: {e}")
    
    def send_command(self, command: str, wait_time: float = 1.0) -> str:
        """Send command and return output"""
        if not self.shell:
            raise RuntimeError("Not connected")
        
        logger.debug(f"Sending command: {command}")
        self.shell.send(command + '\n')
        time.sleep(wait_time)
        
        output = ""
        while self.shell.recv_ready():
            chunk = self.shell.recv(65535).decode('utf-8', errors='ignore')
            output += chunk
            time.sleep(0.1)
        
        return output
    
    def enter_enable_mode(self, prompts: List[str]) -> bool:
        """Enter privileged exec mode"""
        try:
            logger.info("Entering enable mode")
            
            # Send enable command
            output = self.send_command("enable", wait_time=2.0)
            
            # Check if password is required
            if "password" in output.lower() or ":" in output:
                if self.enable_password:
                    logger.debug("Sending enable password")
                    output = self.send_command(self.enable_password, wait_time=1.0)
                else:
                    logger.warning("Enable password required but not provided")
            
            # Verify we're in enable mode (should see # prompt)
            test_output = self.send_command("", wait_time=0.5)
            if any(prompt in test_output for prompt in ['#']):
                logger.info("Enable mode entered successfully")
                return True
            
            logger.warning("Could not verify enable mode")
            return True  # Continue anyway
            
        except Exception as e:
            logger.error(f"Failed to enter enable mode: {e}")
            raise
    
    def disable_paging(self, commands: List[str]) -> bool:
        """Disable paging for long outputs"""
        try:
            for cmd in commands:
                logger.debug(f"Disabling paging with: {cmd}")
                self.send_command(cmd, wait_time=1.0)
            return True
        except Exception as e:
            logger.warning(f"Failed to disable paging: {e}")
            return False
    
    def get_running_config(self, paging_indicators: List[str]) -> str:
        """Retrieve running configuration with automatic paging handling"""
        try:
            logger.info("Retrieving running configuration")
            
            # Send show running-config command
            self.shell.send("show running-config\n")
            time.sleep(1)
            
            output = ""
            max_iterations = 500  # Increased for large configs
            iteration = 0
            no_data_count = 0
            last_output_len = 0
            
            while iteration < max_iterations:
                if self.shell.recv_ready():
                    chunk = self.shell.recv(65535).decode('utf-8', errors='ignore')
                    output += chunk
                    no_data_count = 0
                    
                    # Get last few lines to check for paging
                    last_lines = output.split('\n')[-3:]
                    last_text = '\n'.join(last_lines)
                    
                    # Check for paging indicators (More prompts)
                    paging_detected = False
                    for indicator in paging_indicators:
                        if indicator in chunk or indicator in last_text:
                            logger.info(f"Paging detected: '{indicator}' in output, sending space")
                            self.shell.send(" ")
                            time.sleep(0.3)
                            paging_detected = True
                            break
                    
                    # Also check for common paging patterns (case insensitive)
                    if not paging_detected:
                        chunk_lower = chunk.lower()
                        last_text_lower = last_text.lower()
                        # Check for any form of "more" prompt in chunk or last text
                        if "more:" in chunk_lower or "more:" in last_text_lower:
                            logger.info(f"Allied Telesis paging detected! Last 100 chars: {repr(output[-100:])}")
                            self.shell.send(" ")
                            time.sleep(0.3)
                            paging_detected = True
                        elif "more" in chunk_lower or "continue" in chunk_lower or "next" in chunk_lower:
                            logger.info(f"Generic paging detected in chunk: {repr(chunk[-80:])}")
                            self.shell.send(" ")
                            time.sleep(0.3)
                            paging_detected = True
                    
                    # Check if output stopped (end of config)
                    if not paging_detected:
                        # Check for prompt at the end (indicating completion)
                        last_line = last_lines[-1].strip() if last_lines else ""
                        if last_line.endswith('#') or last_line.endswith('>'):
                            # Only break if it's a short line (actual prompt, not config)
                            if len(last_line) < 50:
                                logger.debug(f"Detected prompt: '{last_line}', output complete")
                                break
                else:
                    no_data_count += 1
                    # If no data for 5 iterations, check if we're done
                    if no_data_count >= 5:
                        if len(output) > 500:
                            logger.debug("No more data, checking for completion")
                            last_lines = output.split('\n')[-3:]
                            if any(line.strip().endswith('#') or line.strip().endswith('>') for line in last_lines):
                                break
                    
                    # Check if output has stopped growing
                    if len(output) == last_output_len and len(output) > 500:
                        logger.debug("Output stopped growing, assuming complete")
                        break
                    last_output_len = len(output)
                    
                    # If stuck for too long, try sending space
                    if no_data_count >= 3 and len(output) > 0:
                        logger.debug("Timeout, trying space to continue paging")
                        self.shell.send(" ")
                        time.sleep(0.5)
                        no_data_count = 0
                    else:
                        time.sleep(0.3)
                
                iteration += 1
            
            if iteration >= max_iterations:
                logger.warning("Max iterations reached while fetching config")
            
            # Clean up output
            output = self._clean_output(output, paging_indicators)
            
            logger.info(f"Retrieved configuration: {len(output)} bytes after {iteration} iterations")
            return output
            
        except Exception as e:
            logger.error(f"Failed to get running config: {e}")
            raise
    
    def _clean_output(self, output: str, paging_indicators: List[str]) -> str:
        """Clean up output by removing prompts and paging artifacts"""
        lines = output.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip paging indicators
            if any(indicator in line for indicator in paging_indicators):
                continue
            
            # Skip command echo
            if line.strip() == "show running-config":
                continue
            
            # Skip prompt lines (ending with # or >)
            if line.strip().endswith('#') or line.strip().endswith('>'):
                if len(line.strip()) < 50:  # Short lines are likely prompts
                    continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def disconnect(self):
        """Close SSH connection"""
        try:
            if self.shell:
                self.shell.close()
            if self.client:
                self.client.close()
            logger.info(f"Disconnected from {self.host}")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
