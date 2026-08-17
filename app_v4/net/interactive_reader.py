from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Sequence


class IncompleteOutputError(RuntimeError):
    """Raised when an interactive command ends without a terminal prompt."""


_ANSI_ESCAPE_RE = re.compile(
    r"(?:\x1B\[[0-?]*[ -/]*[@-~]|\x1B\][^\x07]*(?:\x07|\x1B\\))"
)
_PROMPT_LINE_RE = re.compile(r"^\s*[A-Za-z0-9_.:@/()[\]{}-]*(?:#|>)\s*$")
_GENERIC_PAGING_PATTERNS = (
    re.compile(r"^\s*--\s*more\s*--(?:\s*[,.:].*)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*more\s*:\s*(?:<\s*space\s*>)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*press\s+(?:any\s+key|space).*(?:more|continue)?\s*[.:!?]*\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:continue|next)\s*[:?]?\s*$", re.IGNORECASE),
)


def strip_terminal_control(text: str) -> str:
    """Remove terminal escape sequences and normalize line endings."""
    text = _ANSI_ESCAPE_RE.sub("", text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalized_lines(text: str) -> list[str]:
    return strip_terminal_control(text).split("\n")


def _last_non_empty_line(text: str) -> str:
    for line in reversed(_normalized_lines(text)):
        if line.strip():
            return line
    return ""


def has_terminal_prompt(
    text: str,
    prompt_indicators: Sequence[str] = (),
    allow_bare_prompt: bool = False,
) -> bool:
    """Return whether the last non-empty line looks like a CLI prompt."""
    line = _last_non_empty_line(text)
    stripped_line = line.strip()
    if stripped_line in {"#", ">"} and not allow_bare_prompt:
        return False
    if not _PROMPT_LINE_RE.match(line):
        return False
    if not prompt_indicators:
        return True
    normalized_line = stripped_line.casefold()
    return any(
        normalized_line.endswith(strip_terminal_control(prompt).strip().casefold())
        for prompt in prompt_indicators
        if prompt.strip()
    )


def is_password_prompt(text: str) -> bool:
    """Return whether the current tail is a password-entry prompt."""
    line = _last_non_empty_line(text).strip().casefold()
    return line.endswith(("password:", "passwd:", "passcode:", "pass:"))


def _matches_configured_indicator(line: str, indicator: str) -> bool:
    indicator = strip_terminal_control(indicator).strip()
    if not indicator:
        return False
    lowered_line = line.casefold()
    lowered_indicator = indicator.casefold()
    position = lowered_line.find(lowered_indicator)
    if position < 0:
        return False

    before = line[:position].strip()
    # A configured marker is a paging prompt when it is the whole line,
    # is preceded by a device prompt, or is itself a conventional label.
    if not before:
        return True
    return before.endswith(("#", ">")) or before.casefold().startswith(("more", "press", "quit"))


def is_paging_prompt(text: str, indicators: Sequence[str]) -> bool:
    """Detect a paging prompt only on the current terminal-output tail."""
    line = _last_non_empty_line(text)
    if not line or len(line.strip()) > 160:
        return False
    if any(_matches_configured_indicator(line, indicator) for indicator in indicators):
        return True
    return any(pattern.match(line) for pattern in _GENERIC_PAGING_PATTERNS)


def clean_interactive_output(
    text: str,
    indicators: Sequence[str],
    prompt_indicators: Sequence[str] = (),
    allow_bare_prompt: bool = False,
) -> str:
    """Remove command echo, paging prompts, terminal prompts and control codes."""
    cleaned: list[str] = []
    for line in _normalized_lines(text):
        stripped = line.strip()
        if stripped.casefold() == "show running-config":
            continue
        if stripped and is_paging_prompt(line, indicators):
            continue
        if stripped and has_terminal_prompt(line, prompt_indicators, allow_bare_prompt):
            continue
        cleaned.append(line.rstrip())

    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()
    return "\n".join(cleaned)


async def read_interactive_output(
    read_chunk: Callable[[int], Awaitable[str]],
    send: Callable[[str], object],
    paging_indicators: Sequence[str],
    *,
    command_timeout: float,
    read_timeout: float,
    prompt_indicators: Sequence[str] = (),
    allow_bare_prompt: bool = False,
    chunk_size: int = 8192,
) -> str:
    """Drain a CLI command until a prompt is received.

    The old reader treated one-second gaps and a handful of empty reads as
    successful completion. That truncates configurations on slower switches.
    This reader uses an overall command deadline plus an idle/read deadline,
    and sends a continuation key only when the current tail is an actual
    paging prompt. A command without a terminal prompt is never reported as a
    complete backup.
    """
    if command_timeout <= 0:
        raise ValueError("command_timeout must be greater than zero")
    if read_timeout <= 0:
        raise ValueError("read_timeout must be greater than zero")

    output = ""
    deadline = time.monotonic() + command_timeout
    last_data_at = time.monotonic()

    while True:
        now = time.monotonic()
        remaining_command = deadline - now
        remaining_idle = read_timeout - (now - last_data_at)
        if remaining_command <= 0:
            break
        if remaining_idle <= 0:
            raise IncompleteOutputError(
                f"Timed out waiting for command output after {read_timeout:g}s without data"
            )

        wait_timeout = min(remaining_command, remaining_idle)
        try:
            chunk = await asyncio.wait_for(read_chunk(chunk_size), timeout=wait_timeout)
        except asyncio.TimeoutError:
            if has_terminal_prompt(output, prompt_indicators, allow_bare_prompt):
                return output
            raise IncompleteOutputError(
                f"Timed out waiting for terminal prompt after {read_timeout:g}s"
            )

        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8", errors="replace")
        if not chunk:
            # An empty read can be a transient condition in telnetlib3. Do not
            # use it as an end marker; yield briefly and keep the same idle
            # deadline so repeated empty reads cannot spin the event loop.
            if has_terminal_prompt(output, prompt_indicators, allow_bare_prompt):
                return output
            await asyncio.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
            continue

        output += chunk
        last_data_at = time.monotonic()

        if is_paging_prompt(output, paging_indicators):
            send(" ")
            await asyncio.sleep(0.05)
            continue

        if has_terminal_prompt(output, prompt_indicators, allow_bare_prompt):
            return output

    if has_terminal_prompt(output, prompt_indicators, allow_bare_prompt):
        return output
    raise IncompleteOutputError(
        f"Command exceeded its {command_timeout:g}s deadline before the terminal prompt"
    )
