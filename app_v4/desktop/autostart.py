from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCHTASKS_TASK_NAME = "NCM v4 Backend"


@dataclass(frozen=True)
class AutostartConfig:
    executable: Path
    run_at_startup: bool = True
    run_at_logon: bool = False

    def __post_init__(self) -> None:
        if not self.run_at_startup and not self.run_at_logon:
            raise ValueError("AutostartConfig must enable at least one trigger")


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
    """Build a `schtasks /Create` command line for the headless backend.

    The task runs the desktop executable with `--serve`, which is the headless
    entrypoint. /RL HIGHEST is required so the task can bind a privileged port
    and so DPAPI works against the SYSTEM/admin profile that owns the install.
    /F overwrites the existing definition so re-enabling is idempotent.
    """
    exe = _quote(str(config.executable))
    return [
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


def build_query_command() -> list[str]:
    return ["schtasks", "/Query", "/TN", SCHTASKS_TASK_NAME]


def build_delete_command() -> list[str]:
    return ["schtasks", "/Delete", "/TN", SCHTASKS_TASK_NAME, "/F"]


def parse_query_output(*, returncode: int, stdout: str, stderr: str) -> AutostartStatus:
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
