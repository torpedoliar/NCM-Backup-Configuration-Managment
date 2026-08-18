from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from app_v4.core.config import Settings


@dataclass(frozen=True)
class AppPaths:
    base_dir: Path
    data_dir: Path
    logs_dir: Path
    backups_dir: Path
    static_dir: Path
    database_file: Path
    master_envelope_file: Path
    master_key_file: Path
    scheduler_lock_file: Path


def _resolve_static_dir(base_dir: Path) -> Path:
    """Locate the bundled SPA static directory.

    Under PyInstaller, datas=[(static_dir, "app_v4/service/static")] places the
    bundle at sys._MEIPASS/app_v4/service/static — NOT next to the executable.
    Fall back to base_dir for dev mode.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "app_v4" / "service" / "static"
    return base_dir / "app_v4" / "service" / "static"


def resolve_paths(settings: Settings) -> AppPaths:
    base_dir = settings.base_dir
    backup_root = Path(settings.backup_root_folder)
    backups_dir = backup_root if backup_root.is_absolute() else base_dir / backup_root
    return AppPaths(
        base_dir=base_dir,
        data_dir=base_dir / "data",
        logs_dir=base_dir / "logs",
        backups_dir=backups_dir,
        static_dir=_resolve_static_dir(base_dir),
        database_file=base_dir / "data" / "app.db",
        master_envelope_file=base_dir / "data" / "master.dpapi",
        master_key_file=base_dir / "data" / "master.key",
        scheduler_lock_file=base_dir / "data" / "scheduler.lock",
    )
