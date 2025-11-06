"""Telnet client for switch connections"""
import logging
import asyncio
import time
from typing import Optional, List
import telnetlib3

logger = logging.getLogger(__name__)


class TelnetClient:
    """Telnet connection handler for network devices"""
    
    def __init__(self, host: str, port: int, username: str, password: str,
                 enable_password: str = "", timeout: int = 15):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.timeout = timeout
        self.reader = None
        self.writer = None
    
    async def connect(self) -> bool:
        """Establish Telnet connection"""
        try:
            logger.info(f"[TELNET] Connecting to {self.host}:{self.port}")
            
            # Step 1: Open connection
            logger.info(f"[TELNET] Opening TCP connection (timeout={self.timeout}s)...")
            self.reader, self.writer = await asyncio.wait_for(
                telnetlib3.open_connection(
                    self.host,
                    self.port,
                    connect_minwait=0.5
                ),
                timeout=self.timeout
            )
            logger.info(f"[TELNET] TCP connection established")
            
            # Step 2: Wait for login prompt
            logger.info(f"[TELNET] Waiting for login prompt...")
            await asyncio.sleep(1)
            initial = await self._read_until_prompt(["ogin:", "sername:"], timeout=5)
            logger.info(f"[TELNET] Login prompt received")
            
            # Step 3: Send username
            logger.info(f"[TELNET] Sending username...")
            self.writer.write(self.username + '\n')
            await asyncio.sleep(0.5)
            
            # Step 4: Wait for password prompt
            logger.info(f"[TELNET] Waiting for password prompt...")
            await self._read_until_prompt(["assword:"], timeout=5)
            logger.info(f"[TELNET] Password prompt received")
            
            # Step 5: Send password
            logger.info(f"[TELNET] Sending password...")
            self.writer.write(self.password + '\n')
            await asyncio.sleep(1)
            
            # Step 6: Check if login successful
            logger.info(f"[TELNET] Checking authentication result...")
            response = await self._read_available(timeout=2)
            if "failed" in response.lower() or "incorrect" in response.lower():
                logger.error(f"[TELNET] Authentication failed")
                raise ConnectionError("Authentication failed")
            
            logger.info(f"[TELNET] Successfully connected and authenticated to {self.host}")
            return True
            
        except asyncio.TimeoutError as e:
            logger.error(f"[TELNET] Connection timeout to {self.host}:{self.port}")
            raise ConnectionError(f"Telnet connection timeout: {e}")
        except Exception as e:
            logger.error(f"[TELNET] Connection failed to {self.host}: {e}")
            raise ConnectionError(f"Telnet connection failed: {e}")
    
    async def _read_until_prompt(self, prompts: List[str], timeout: int = 5) -> str:
        """Read until one of the prompts is found"""
        output = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                chunk = await asyncio.wait_for(
                    self.reader.read(1024),
                    timeout=0.5
                )
                output += chunk
                
                if any(prompt.lower() in output.lower() for prompt in prompts):
                    return output
            except asyncio.TimeoutError:
                continue
        
        return output
    
    async def _read_available(self, timeout: int = 2) -> str:
        """Read all available data"""
        output = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                chunk = await asyncio.wait_for(
                    self.reader.read(8192),
                    timeout=0.3
                )
                if chunk:
                    output += chunk
                else:
                    break
            except asyncio.TimeoutError:
                break
        
        return output
    
    async def send_command(self, command: str, wait_time: float = 1.0) -> str:
        """Send command and return output"""
        if not self.writer:
            raise RuntimeError("Not connected")
        
        logger.debug(f"Sending command: {command}")
        self.writer.write(command + '\n')
        await asyncio.sleep(wait_time)
        
        output = await self._read_available(timeout=3)
        return output
    
    async def enter_enable_mode(self, prompts: List[str]) -> bool:
        """Enter privileged exec mode"""
        try:
            logger.info("Entering enable mode")
            
            # Send enable command
            output = await self.send_command("enable", wait_time=2.0)
            
            # Check if password is required
            if "password" in output.lower() or ":" in output:
                if self.enable_password:
                    logger.debug("Sending enable password")
                    output = await self.send_command(self.enable_password, wait_time=1.0)
                else:
                    logger.warning("Enable password required but not provided")
            
            logger.info("Enable mode entered")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enter enable mode: {e}")
            raise
    
    async def disable_paging(self, commands: List[str]) -> bool:
        """Disable paging for long outputs"""
        try:
            for cmd in commands:
                logger.debug(f"Disabling paging with: {cmd}")
                await self.send_command(cmd, wait_time=1.0)
            return True
        except Exception as e:
            logger.warning(f"Failed to disable paging: {e}")
            return False
    
    async def get_running_config(self, paging_indicators: List[str]) -> str:
        """Retrieve running configuration with automatic paging handling"""
        try:
            logger.info("Retrieving running configuration")
            
            # Send show running-config command
            self.writer.write("show running-config\n")
            await asyncio.sleep(1)
            
            output = ""
            max_iterations = 500  # Increased for large configs
            iteration = 0
            no_data_count = 0
            last_output_len = 0
            
            while iteration < max_iterations:
                try:
                    chunk = await asyncio.wait_for(
                        self.reader.read(8192),
                        timeout=1.0
                    )
                    
                    if chunk:
                        output += chunk
                        no_data_count = 0
                        
                        # Log chunk for debugging
                        logger.debug(f"Received chunk ({len(chunk)} bytes): {repr(chunk[-100:])}")
                        
                        # Get last few lines to check for paging
                        last_lines = output.split('\n')[-3:]
                        last_text = '\n'.join(last_lines)
                        
                        # Check for paging indicators (More prompts)
                        paging_detected = False
                        for indicator in paging_indicators:
                            if indicator in chunk or indicator in last_text:
                                logger.info(f"Paging detected: '{indicator}' in output, sending space")
                                self.writer.write(" ")
                                await asyncio.sleep(0.3)
                                paging_detected = True
                                break
                        
                        # Also check for common paging patterns (case insensitive)
                        if not paging_detected:
                            chunk_lower = chunk.lower()
                            last_text_lower = last_text.lower()
                            # Check for any form of "more" prompt in chunk or last text
                            if "more:" in chunk_lower or "more:" in last_text_lower:
                                logger.info(f"Allied Telesis paging detected! Last 100 chars: {repr(output[-100:])}")
                                self.writer.write(" ")
                                await asyncio.sleep(0.3)
                                paging_detected = True
                            elif "more" in chunk_lower or "continue" in chunk_lower or "next" in chunk_lower:
                                logger.info(f"Generic paging detected in chunk: {repr(chunk[-80:])}")
                                self.writer.write(" ")
                                await asyncio.sleep(0.3)
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
                            if len(output) > 100:
                                logger.debug("No more data, assuming output complete")
                                break
                        await asyncio.sleep(0.3)
                    
                except asyncio.TimeoutError:
                    no_data_count += 1
                    # Check if output has stopped growing
                    if len(output) == last_output_len and len(output) > 500:
                        logger.debug("Output stopped growing, checking for completion")
                        last_lines = output.split('\n')[-3:]
                        if any(line.strip().endswith('#') or line.strip().endswith('>') for line in last_lines):
                            break
                    last_output_len = len(output)
                    
                    # If stuck for too long, try sending space
                    if no_data_count >= 3 and len(output) > 0:
                        logger.debug("Timeout, trying space to continue paging")
                        self.writer.write(" ")
                        await asyncio.sleep(0.5)
                        no_data_count = 0
                
                iteration += 1
            
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
            
            # Skip prompt lines
            if line.strip().endswith('#') or line.strip().endswith('>'):
                if len(line.strip()) < 50:
                    continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    async def disconnect(self):
        """Close Telnet connection"""
        try:
            if self.writer:
                self.writer.close()
            logger.info(f"Disconnected from {self.host}")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
