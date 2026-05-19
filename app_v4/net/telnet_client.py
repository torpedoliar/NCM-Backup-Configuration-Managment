from __future__ import annotations

import asyncio

import telnetlib3


class AsyncTelnetClient:
    def __init__(self, host: str, port: int, username: str, password: str, enable_password: str = "", timeout: int = 15):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.timeout = timeout
        self.reader = None
        self.writer = None

    async def connect(self) -> bool:
        self.reader, self.writer = await asyncio.wait_for(
            telnetlib3.open_connection(self.host, self.port, connect_minwait=0.5),
            timeout=self.timeout,
        )
        await asyncio.sleep(0.2)
        await self._read_until(["login:", "username:"], timeout=5)
        self.writer.write(self.username + "\n")
        await self._read_until(["password:"], timeout=5)
        self.writer.write(self.password + "\n")
        response = await self._read_available(timeout=2)
        if "failed" in response.lower() or "incorrect" in response.lower():
            raise ConnectionError("Telnet authentication failed")
        return True

    async def enter_enable_mode(self, prompts: list[str]) -> bool:
        if self.enable_password:
            self.writer.write("enable\n")
            await asyncio.sleep(0.2)
            output = await self._read_available(timeout=2)
            if "password" in output.lower():
                self.writer.write(self.enable_password + "\n")
                await asyncio.sleep(0.2)
        return True

    async def disable_paging(self, commands: list[str]) -> bool:
        for command in commands:
            self.writer.write(command + "\n")
            await asyncio.sleep(0.1)
            await self._read_available(timeout=1)
        return True

    async def get_running_config(self, paging_indicators: list[str]) -> str:
        self.writer.write("show running-config\n")
        output = ""
        for _ in range(500):
            chunk = await self._read_available(timeout=1)
            output += chunk
            if any(indicator in chunk for indicator in paging_indicators):
                self.writer.write(" ")
                continue
            tail = output.splitlines()[-3:] if output else []
            if any((line.strip().endswith("#") or line.strip().endswith(">")) and len(line.strip()) < 50 for line in tail):
                break
            if not chunk and len(output) > 100:
                break
        return self._clean_output(output, paging_indicators)

    async def disconnect(self) -> None:
        if self.writer is not None:
            self.writer.close()

    async def _read_until(self, prompts: list[str], timeout: int) -> str:
        output = ""
        end = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < end:
            try:
                chunk = await asyncio.wait_for(self.reader.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            output += chunk
            if any(prompt.lower() in output.lower() for prompt in prompts):
                return output
        return output

    async def _read_available(self, timeout: int) -> str:
        output = ""
        while True:
            try:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=timeout)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            output += chunk
            if len(chunk) < 4096:
                break
        return output

    def _clean_output(self, output: str, paging_indicators: list[str]) -> str:
        lines = []
        for line in output.split("\n"):
            stripped = line.strip()
            if stripped == "show running-config":
                continue
            if any(indicator in line for indicator in paging_indicators):
                continue
            if (stripped.endswith("#") or stripped.endswith(">")) and len(stripped) < 50:
                continue
            lines.append(line)
        return "\n".join(lines)
