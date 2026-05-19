from __future__ import annotations

import asyncio

import asyncssh


class AsyncSshClient:
    def __init__(self, host: str, port: int, username: str, password: str, enable_password: str = "", timeout: int = 15):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.timeout = timeout
        self.conn: asyncssh.SSHClientConnection | None = None

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
        return True

    async def disable_paging(self, commands: list[str]) -> bool:
        if self.conn is None:
            raise RuntimeError("Not connected")
        for command in commands:
            await self.conn.run(command, check=False)
        return True

    async def get_running_config(self, paging_indicators: list[str]) -> str:
        if self.conn is None:
            raise RuntimeError("Not connected")
        result = await self.conn.run("show running-config", check=False)
        if result.exit_status not in (0, None):
            raise RuntimeError(result.stderr or f"show running-config failed with {result.exit_status}")
        return str(result.stdout)

    async def disconnect(self) -> None:
        if self.conn is not None:
            self.conn.close()
            await self.conn.wait_closed()
            self.conn = None
