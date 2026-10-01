from __future__ import annotations

import asyncio
import contextlib
import logging

import asyncssh

from app_v4.net.interactive_reader import strip_terminal_control

logger = logging.getLogger(__name__)


class AsyncMikrotikClient:
    """Backup client for MikroTik RouterOS.

    Performs dual backup:
    1. Text config via `/export compact` (human-readable, diffable).
    2. Binary backup via `/system backup save` + SFTP download.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        enable_password: str = "",
        timeout: float = 15,
        command_timeout: float = 60,
        read_timeout: float = 30,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.timeout = timeout
        self.command_timeout = command_timeout
        self.read_timeout = read_timeout
        self.conn: asyncssh.SSHClientConnection | None = None
        self.binary_bytes: bytes | None = None

    async def connect(self) -> bool:
        self.conn = await asyncio.wait_for(
            asyncssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                known_hosts=None,
            ),
            timeout=self.timeout,
        )
        return True

    async def enter_enable_mode(self, prompts: list[str]) -> bool:
        # RouterOS does not have Cisco-style enable mode
        return True

    async def disable_paging(self, commands: list[str]) -> bool:
        # Direct command execution via conn.run bypasses interactive paging
        return True

    async def get_running_config(self, paging_indicators: list[str]) -> str:
        if self.conn is None:
            raise RuntimeError("Not connected")

        # 1. Fetch text configuration via /export compact
        res = await asyncio.wait_for(
            self.conn.run("/export compact", check=False),
            timeout=self.command_timeout,
        )
        text = res.stdout or ""
        if not text.strip():
            # Fallback to plain /export if compact produced nothing
            res = await asyncio.wait_for(
                self.conn.run("/export", check=False),
                timeout=self.command_timeout,
            )
            text = res.stdout or ""

        text = strip_terminal_control(text).strip()

        # 2. Attempt binary backup (.backup) via SFTP
        await self._fetch_binary_backup()

        return text

    async def _fetch_binary_backup(self) -> None:
        if self.conn is None:
            return
        temp_name = "ncm_backup_temp"
        try:
            # Generate binary backup on router
            await asyncio.wait_for(
                self.conn.run(
                    f"/system backup save name={temp_name} encryption=none",
                    check=False,
                ),
                timeout=15.0,
            )
            await asyncio.sleep(1.0)

            # Download via SFTP
            async with self.conn.start_sftp_client() as sftp:
                target_file = f"{temp_name}.backup"
                if await sftp.exists(target_file):
                    async with sftp.open(target_file, "rb") as f:
                        self.binary_bytes = await f.read()
        except Exception as exc:  # noqa: BLE001
            logger.warning("MikroTik binary backup download via SFTP failed: %s", exc)
        finally:
            with contextlib.suppress(Exception):
                await self.conn.run(
                    f'/file remove [find name~"{temp_name}"]',
                    check=False,
                )

    async def disconnect(self) -> None:
        if self.conn is not None:
            self.conn.close()
            with contextlib.suppress(Exception):
                await self.conn.wait_closed()
            self.conn = None
