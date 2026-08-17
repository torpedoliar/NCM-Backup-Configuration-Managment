from __future__ import annotations

import asyncio
import logging
import time

import telnetlib3

from app_v4.net.interactive_reader import (
    clean_interactive_output,
    has_terminal_prompt,
    is_password_prompt,
    read_interactive_output,
    strip_terminal_control,
)


logger = logging.getLogger(__name__)


class AsyncTelnetClient:
    """Telnet client tuned for Allied Telesis switches.

    Why the v3-style sequence: AlliedWare (and many embedded CLIs) reply with
    `% Invalid input` when an unsupported paging command is sent — that is
    NOT a fatal error, only a hint that the command does not exist on this
    OS. We try several variants (`terminal length 0`, `set length 0`,
    `terminal pager 0`, `no page`) and let the device pick whichever works.
    The runner only fails if `show running-config` itself returns nothing
    usable.
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
        self.prompt_indicators: list[str] = ["#", ">"]
        self.allow_bare_prompt = False
        self.reader = None
        self.writer = None

    async def connect(self) -> bool:
        logger.info("[TELNET] Connecting to %s:%s", self.host, self.port)
        self.reader, self.writer = await asyncio.wait_for(
            telnetlib3.open_connection(self.host, self.port, connect_minwait=0.5),
            timeout=self.timeout,
        )
        await asyncio.sleep(1)
        await self._read_until(["ogin:", "sername:"], timeout=min(5.0, self.read_timeout))
        self.writer.write(self.username + "\n")
        await asyncio.sleep(0.5)
        await self._read_until(["assword:"], timeout=min(5.0, self.read_timeout))
        self.writer.write(self.password + "\n")
        await asyncio.sleep(1)
        response = await self._read_until(
            ["failed", "incorrect", "#", ">"],
            timeout=min(5.0, self.read_timeout),
        )
        if "failed" in response.lower() or "incorrect" in response.lower():
            raise ConnectionError("Telnet authentication failed")
        return True

    async def enter_enable_mode(self, prompts: list[str]) -> bool:
        self.prompt_indicators = prompts or ["#", ">"]
        self.writer.write("enable\n")
        await asyncio.sleep(0.5)
        output = await self._read_until(
            ["password", "#", ">"],
            timeout=min(5.0, self.read_timeout),
        )
        self._remember_bare_prompt(output)
        if is_password_prompt(output):
            if self.enable_password:
                self.writer.write(self.enable_password + "\n")
                await asyncio.sleep(0.5)
                output = await self._read_until(
                    ["#", ">"],
                    timeout=min(5.0, self.read_timeout),
                )
                self._remember_bare_prompt(output)
        return True

    async def disable_paging(self, commands: list[str]) -> bool:
        """Try every paging-disable command. % Invalid input is non-fatal."""
        any_accepted = False
        for command in commands:
            self.writer.write(command + "\n")
            await asyncio.sleep(0.3)
            output = await self._read_until(
                ["#", ">"],
                timeout=min(3.0, self.read_timeout),
            )
            lower = output.lower()
            if "invalid input" in lower or "unrecognized" in lower or "incomplete" in lower:
                logger.debug("paging command rejected: %s", command)
                continue
            any_accepted = True
        return any_accepted

    async def get_running_config(self, paging_indicators: list[str]) -> str:
        if self.reader is None or self.writer is None:
            raise RuntimeError("Not connected")
        self.writer.write("show running-config\n")
        output = await read_interactive_output(
            self.reader.read,
            self.writer.write,
            paging_indicators,
            command_timeout=self.command_timeout,
            read_timeout=self.read_timeout,
            prompt_indicators=self.prompt_indicators,
            allow_bare_prompt=self.allow_bare_prompt,
        )
        return clean_interactive_output(
            output,
            paging_indicators,
            prompt_indicators=self.prompt_indicators,
            allow_bare_prompt=self.allow_bare_prompt,
        )

    async def disconnect(self) -> None:
        if self.writer is not None:
            try:
                self.writer.close()
            except Exception:
                pass

    def _remember_bare_prompt(self, output: str) -> None:
        last_line = ""
        for line in reversed(strip_terminal_control(output).split("\n")):
            if line.strip():
                last_line = line.strip()
                break
        if last_line in {"#", ">"}:
            self.allow_bare_prompt = True

    async def _read_until(self, prompts: list[str], timeout: float) -> str:
        if self.reader is None:
            raise RuntimeError("Not connected")
        output = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = await asyncio.wait_for(self.reader.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if not chunk:
                await asyncio.sleep(0.05)
                continue
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8", errors="replace")
            output += chunk
            if any(prompt.lower() in {"#", ">"} for prompt in prompts) and has_terminal_prompt(
                output,
                self.prompt_indicators,
                True,
            ):
                return output
            lowered = output.lower()
            if any(
                prompt.lower() not in {"#", ">"} and prompt.lower() in lowered
                for prompt in prompts
            ):
                return output
        return output

    async def _read_available(self, timeout: float) -> str:
        if self.reader is None:
            raise RuntimeError("Not connected")
        output = ""
        deadline = time.monotonic() + timeout
        last_data_at = time.monotonic()
        idle_timeout = min(timeout, max(0.2, min(self.read_timeout, 1.5)))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                chunk = await asyncio.wait_for(self.reader.read(8192), timeout=min(0.3, remaining))
            except asyncio.TimeoutError:
                break
            if not chunk:
                if time.monotonic() - last_data_at >= idle_timeout:
                    break
                await asyncio.sleep(0.05)
                continue
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8", errors="replace")
            output += chunk
            last_data_at = time.monotonic()
        return output

    def _clean_output(self, output: str, paging_indicators: list[str]) -> str:
        # Kept as a compatibility helper for callers that used the old client
        # private method; the actual command path uses the shared reader.
        return clean_interactive_output(
            output,
            paging_indicators,
            prompt_indicators=self.prompt_indicators,
            allow_bare_prompt=self.allow_bare_prompt,
        )
