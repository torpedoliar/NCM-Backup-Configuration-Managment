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
class AuthSettings:
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    lockout_threshold: int = 5
    lockout_window_minutes: int = 10
    lockout_duration_minutes: int = 30
    password_min_length: int = 8
    password_require_upper: bool = True
    password_require_lower: bool = True
    password_require_digit: bool = True
    password_require_symbol: bool = False


@dataclass(frozen=True)
class RuntimeSettings:
    retention: RetentionSettings = field(default_factory=RetentionSettings)
    auth: AuthSettings = field(default_factory=AuthSettings)


def load_runtime_settings(path: Path) -> RuntimeSettings:
    if not path.exists():
        return RuntimeSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        retention_data = data.get("retention", {})
        auth_data = data.get("auth", {})
        return RuntimeSettings(
            retention=RetentionSettings(**{
                k: v for k, v in retention_data.items()
                if k in RetentionSettings.__dataclass_fields__
            }),
            auth=AuthSettings(**{
                k: v for k, v in auth_data.items()
                if k in AuthSettings.__dataclass_fields__
            }),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return RuntimeSettings()


def save_runtime_settings(path: Path, settings: RuntimeSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
