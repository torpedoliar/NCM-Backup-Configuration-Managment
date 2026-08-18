from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from app_v4.desktop.autostart import (
    AutostartConfig,
    AutostartMethod,
    AutostartStatus,
    build_create_command,
    build_delete_command,
    build_query_command,
    parse_query_output,
)


@dataclass(frozen=True)
class AutostartActionResult:
    ok: bool
    status: AutostartStatus
    message: str


CommandResult = tuple[int, str, str]
RunCommand = Callable[[list[str]], Awaitable[CommandResult]]


def resolve_executable_path() -> Path | None:
    """Best-effort guess at the bundled desktop executable path.

    PyInstaller sets sys.frozen and writes the exe path into sys.executable.
    When running from source the autostart action is not supported.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return None


async def _run_subprocess(cmd: list[str]) -> CommandResult:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return (
        int(proc.returncode or 0),
        stdout.decode("utf-8", errors="replace") if stdout else "",
        stderr.decode("utf-8", errors="replace") if stderr else "",
    )


async def query_status(*, method: AutostartMethod = "task", run_command: RunCommand | None = None) -> AutostartStatus:
    runner = run_command or _run_subprocess
    rc, out, err = await runner(build_query_command(method))
    return parse_query_output(returncode=rc, stdout=out, stderr=err, method=method)


async def query_any_status(
    *, run_command: RunCommand | None = None
) -> tuple[AutostartStatus, AutostartMethod | None]:
    """Report whichever mechanism is installed: scheduled task first, else Run key."""
    task_status = await query_status(method="task", run_command=run_command)
    if task_status.installed:
        return task_status, "task"
    runkey_status = await query_status(method="runkey", run_command=run_command)
    if runkey_status.installed:
        return runkey_status, "runkey"
    return AutostartStatus(installed=False, ready=False, raw_status=None), None


async def enable_autostart(
    config: AutostartConfig,
    *,
    run_command: RunCommand | None = None,
) -> AutostartActionResult:
    runner = run_command or _run_subprocess
    rc, out, err = await runner(build_create_command(config))
    if rc != 0:
        return AutostartActionResult(
            ok=False,
            status=AutostartStatus(installed=False, ready=False, raw_status=None),
            message=(err or out or "schtasks /Create failed").strip(),
        )
    status = await query_status(method=config.method, run_command=runner)
    return AutostartActionResult(
        ok=status.installed,
        status=status,
        message="Auto-start enabled." if status.installed else "Registered but not visible to the OS.",
    )


async def disable_autostart(*, method: AutostartMethod = "task", run_command: RunCommand | None = None) -> AutostartActionResult:
    runner = run_command or _run_subprocess
    rc, out, err = await runner(build_delete_command(method))
    if rc != 0 and "cannot find" not in (err or "").lower() and "tidak dapat menemukan" not in (err or "").lower():
        return AutostartActionResult(
            ok=False,
            status=AutostartStatus(installed=True, ready=False, raw_status=None),
            message=(err or out or "schtasks /Delete failed").strip(),
        )
    return AutostartActionResult(
        ok=True,
        status=AutostartStatus(installed=False, ready=False, raw_status=None),
        message="Auto-start disabled.",
    )
