from __future__ import annotations

import asyncio
import contextlib
import time

import asyncssh

from app_v4.net.interactive_reader import (
    clean_interactive_output,
    has_terminal_prompt,
    is_password_prompt,
    read_interactive_output,
    strip_terminal_control,
)


class AsyncSshClient:
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
        self.conn: asyncssh.SSHClientConnection | None = None
        self.process = None

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
        self.process = await self.conn.create_process(term_type="vt100")
        await self._read_available(timeout=min(1.0, self.read_timeout))
        return True

    async def enter_enable_mode(self, prompts: list[str]) -> bool:
        self.prompt_indicators = prompts or ["#", ">"]
        self._write("enable\n")
        output = await self._read_until(
            ["password", "#", ">"],
            timeout=min(5.0, self.read_timeout),
        )
        self._remember_bare_prompt(output)
        if is_password_prompt(output):
            if self.enable_password:
                self._write(self.enable_password + "\n")
                output = await self._read_until(
                    ["#", ">"],
                    timeout=min(5.0, self.read_timeout),
                )
                self._remember_bare_prompt(output)
        return True

    async def disable_paging(self, commands: list[str]) -> bool:
        any_accepted = False
        for command in commands:
            self._write(command + "\n")
            output = await self._read_until(
                ["#", ">"],
                timeout=min(3.0, self.read_timeout),
            )
            lower = output.lower()
            if "invalid input" in lower or "unrecognized" in lower or "incomplete" in lower:
                continue
            any_accepted = True
        return any_accepted

    async def get_running_config(self, paging_indicators: list[str]) -> str:
        if self.process is None:
            raise RuntimeError("Not connected")
        self._write("show running-config\n")
        output = await read_interactive_output(
            self.process.stdout.read,
            self._write,
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
        if self.process is not None:
            with contextlib.suppress(Exception):
                self.process.stdin.write("exit\n")
                self.process.stdin.write_eof()
            self.process = None
        if self.conn is not None:
            self.conn.close()
            await self.conn.wait_closed()
            self.conn = None

    def _write(self, text: str) -> None:
        if self.process is None:
            raise RuntimeError("Not connected")
        self.process.stdin.write(text)

    def _remember_bare_prompt(self, output: str) -> None:
        last_line = ""
        for line in reversed(strip_terminal_control(output).split("\n")):
            if line.strip():
                last_line = line.strip()
                break
        if last_line in {"#", ">"}:
            self.allow_bare_prompt = True

    async def _read_until(self, tokens: list[str], timeout: float) -> str:
        if self.process is None:
            raise RuntimeError("Not connected")
        output = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = await asyncio.wait_for(self.process.stdout.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if not chunk:
                await asyncio.sleep(0.05)
                continue
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8", errors="replace")
            output += chunk
            if any(token.lower() in {"#", ">"} for token in tokens) and has_terminal_prompt(
                output,
                self.prompt_indicators,
                True,
            ):
                return output
            lowered = output.lower()
            if any(
                token.lower() not in {"#", ">"} and token.lower() in lowered
                for token in tokens
            ):
                return output
        return output

    async def _read_available(self, timeout: float) -> str:
        if self.process is None:
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
                chunk = await asyncio.wait_for(
                    self.process.stdout.read(8192),
                    timeout=min(0.3, remaining),
                )
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
