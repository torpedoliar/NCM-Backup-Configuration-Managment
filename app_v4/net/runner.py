from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Protocol

from app_v4.core.config import Settings
from app_v4.core.network_config import load_network_config
from app_v4.net.ssh_client import AsyncSshClient
from app_v4.net.telnet_client import AsyncTelnetClient


class BackupClient(Protocol):
    async def connect(self) -> bool: ...
    async def enter_enable_mode(self, prompts: list[str]) -> bool: ...
    async def disable_paging(self, commands: list[str]) -> bool: ...
    async def get_running_config(self, paging_indicators: list[str]) -> str: ...
    async def disconnect(self) -> None: ...


@dataclass(frozen=True)
class BackupRunResult:
    success: bool
    config_text: str
    message: str


class BackupRunner:
    def __init__(self, settings: Settings, client_factory: Callable[..., BackupClient] | None = None):
        self.settings = settings
        self.config = load_network_config(settings)
        self.client_factory = client_factory

    async def execute_backup(
        self,
        protocol: str,
        host: str,
        port: int,
        username: str,
        password: str,
        enable_password: str = "",
    ) -> BackupRunResult:
        protocol = protocol.lower()
        if protocol not in {"ssh", "telnet"}:
            return BackupRunResult(False, "", f"Unsupported protocol in Phase 1: {protocol}")

        last_error = "Backup failed"
        for attempt in range(self.config.max_retries):
            if attempt > 0:
                delay = self.config.retry_delay * (self.config.backoff_multiplier ** (attempt - 1))
                await asyncio.sleep(delay)
            client = self._make_client(protocol, host, port, username, password, enable_password)
            try:
                await client.connect()
                await client.enter_enable_mode(self.config.prompts)
                await client.disable_paging(self.config.paging_disable_commands)
                config_text = await client.get_running_config(self.config.paging_indicators)
                config_text = self._normalize_output(config_text)
                if len(config_text) < 1:
                    raise ValueError("Retrieved configuration is empty")
                return BackupRunResult(True, config_text, "Backup completed successfully")
            except Exception as exc:
                last_error = str(exc)
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass
        return BackupRunResult(False, "", f"Backup failed after {self.config.max_retries} attempts: {last_error}")

    def _make_client(self, protocol: str, host: str, port: int, username: str, password: str, enable_password: str) -> BackupClient:
        if self.client_factory is not None:
            return self.client_factory(
                protocol=protocol,
                host=host,
                port=port,
                username=username,
                password=password,
                enable_password=enable_password,
                timeout=self.config.connect_timeout,
            )
        if protocol == "ssh":
            return AsyncSshClient(host, port, username, password, enable_password, self.config.connect_timeout)
        return AsyncTelnetClient(host, port, username, password, enable_password, self.config.connect_timeout)

    def _normalize_output(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.split("\n")]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)
