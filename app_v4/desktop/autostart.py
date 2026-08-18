from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SCHTASKS_TASK_NAME = "NCM v4 Backend"
RUNKEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUNKEY_VALUE = "NCM v4 Backend"

AutostartMethod = Literal["task", "runkey"]


@dataclass(frozen=True)
class AutostartConfig:
    executable: Path
    run_at_startup: bool = True
    run_at_logon: bool = False
    method: AutostartMethod = "task"
    run_whether_logged_on: bool = False
    username: str | None = None
    password: str | None = None

    def __post_init__(self) -> None:
        if not self.run_at_startup and not self.run_at_logon:
            raise ValueError("AutostartConfig must enable at least one trigger")
        if self.method == "task" and self.run_whether_logged_on and not (self.username and self.password):
            raise ValueError("run_whether_logged_on requires username and password")


@dataclass(frozen=True)
class AutostartStatus:
    installed: bool
    ready: bool
    raw_status: str | None


def _schedule_kind(config: AutostartConfig) -> str:
    return "ONSTART" if config.run_at_startup else "ONLOGON"


def _quote(path: str) -> str:
    if " " in path or "\t" in path:
        return f'"{path}"'
    return path


def build_create_command(config: AutostartConfig) -> list[str]:
    """Build the command that registers the backend with the OS.

    Two mechanisms:

    * ``task`` — a Task Scheduler entry. The default runs at boot/logon only
      while the user is logged on. With ``run_whether_logged_on`` a username
      and password are passed via ``/RU``/``/RP`` so the task runs without any
      interactive logon (schtasks stores the password encrypted).
    * ``runkey`` — an HKCU ``...\\CurrentVersion\\Run`` value that starts the
      backend at logon. Needs no admin and no Task Scheduler rights, which
      matters on hosts where scheduled-task creation is denied by policy.
    """
    exe = _quote(str(config.executable))
    if config.method == "runkey":
        return [
            "reg",
            "add",
            f"HKCU\\{RUNKEY_PATH}",
            "/v",
            RUNKEY_VALUE,
            "/t",
            "REG_SZ",
            "/d",
            f'"{exe}" --serve',
            "/f",
        ]
    cmd = [
        "schtasks",
        "/Create",
        "/TN",
        SCHTASKS_TASK_NAME,
        "/SC",
        _schedule_kind(config),
        "/TR",
        f"{exe} --serve",
        "/RL",
        "HIGHEST",
        "/F",
    ]
    if config.run_whether_logged_on:
        cmd += ["/RU", config.username, "/RP", config.password]
    return cmd


def build_query_command(method: AutostartMethod = "task") -> list[str]:
    if method == "runkey":
        return ["reg", "query", f"HKCU\\{RUNKEY_PATH}", "/v", RUNKEY_VALUE]
    return ["schtasks", "/Query", "/TN", SCHTASKS_TASK_NAME]


def build_delete_command(method: AutostartMethod = "task") -> list[str]:
    if method == "runkey":
        return ["reg", "delete", f"HKCU\\{RUNKEY_PATH}", "/v", RUNKEY_VALUE, "/f"]
    return ["schtasks", "/Delete", "/TN", SCHTASKS_TASK_NAME, "/F"]


def parse_query_output(*, returncode: int, stdout: str, stderr: str, method: AutostartMethod = "task") -> AutostartStatus:
    if method == "runkey":
        if returncode != 0:
            return AutostartStatus(installed=False, ready=False, raw_status=None)
        return AutostartStatus(installed=True, ready=True, raw_status="ready")
    if returncode != 0:
        return AutostartStatus(installed=False, ready=False, raw_status=None)
    text = stdout or ""
    raw_status: str | None = None
    for line in text.splitlines():
        if SCHTASKS_TASK_NAME in line:
            tokens = line.rsplit(None, 1)
            if tokens:
                raw_status = tokens[-1].strip()
            break
    if raw_status is None:
        return AutostartStatus(installed=False, ready=False, raw_status=None)
    ready = raw_status.lower() in {"ready", "running"}
    return AutostartStatus(installed=True, ready=ready, raw_status=raw_status)
