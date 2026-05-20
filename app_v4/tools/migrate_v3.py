from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MigrationResult:
    database_copied: bool
    backups_copied: int
    legacy_passphrase_migrated: bool


def migrate_v3_install(source_dir: Path, target_dir: Path, envelope_store, jwt_secret: bytes) -> MigrationResult:
    source_dir = Path(source_dir)
    target_dir = Path(target_dir)
    data_dir = target_dir / "data"
    backup_target = target_dir / "backups"
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_target.mkdir(parents=True, exist_ok=True)

    database_copied = False
    for candidate in [source_dir / "ncm.db", source_dir / "data" / "ncm.db"]:
        if candidate.exists():
            shutil.copy2(candidate, data_dir / "ncm.db")
            database_copied = True
            break

    backups_copied = 0
    source_backups = source_dir / "backups"
    if source_backups.exists():
        for path in source_backups.rglob("*"):
            if path.is_file():
                relative = path.relative_to(source_backups)
                destination = backup_target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                backups_copied += 1

    legacy_passphrase_migrated = False
    for legacy in [source_dir / ".service_passphrase", source_dir / ".gui_passphrase"]:
        if legacy.exists():
            passphrase = legacy.read_text(encoding="utf-8").strip()
            envelope_store.save(passphrase, jwt_secret)
            legacy.unlink()
            legacy_passphrase_migrated = True
            break

    return MigrationResult(database_copied, backups_copied, legacy_passphrase_migrated)
