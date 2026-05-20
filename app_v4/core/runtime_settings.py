from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RetentionSettings:
    backup_min_keep: int = 1
    backup_retention_days: int = 365
    audit_retention_days: int = 90
    retention_hour: int = 3
    retention_minute: int = 0


@dataclass(frozen=True)
class RuntimeSettings:
    retention: RetentionSettings = field(default_factory=RetentionSettings)


def load_runtime_settings(path: Path) -> RuntimeSettings:
    if not path.exists():
        return RuntimeSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        retention_data = data.get("retention", {})
        return RuntimeSettings(retention=RetentionSettings(**{
            k: v for k, v in retention_data.items()
            if k in RetentionSettings.__dataclass_fields__
        }))
    except (json.JSONDecodeError, TypeError, ValueError):
        return RuntimeSettings()


def save_runtime_settings(path: Path, settings: RuntimeSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
