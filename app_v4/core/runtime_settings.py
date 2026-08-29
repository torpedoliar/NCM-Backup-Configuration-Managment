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
class BackupLocationSettings:
    backup_root_folder: str | None = None


@dataclass(frozen=True)
class TimeSettings:
    timezone: str = "Asia/Jakarta"
    ntp_servers: tuple[str, ...] = ("pool.ntp.org",)
    ntp_enabled: bool = False


@dataclass(frozen=True)
class NotifySettings:
    """Drift notification + review-reminder delivery (webhook / SMTP email)."""

    enabled: bool = False
    webhook_url: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_tls: bool = True
    email_to: tuple[str, ...] = ()
    app_public_url: str = "http://127.0.0.1:8443"
    review_reminder_hour: int = 9
    review_reminder_minute: int = 0


@dataclass(frozen=True)
class RuntimeSettings:
    retention: RetentionSettings = field(default_factory=RetentionSettings)
    auth: AuthSettings = field(default_factory=AuthSettings)
    backup_location: BackupLocationSettings = field(default_factory=BackupLocationSettings)
    time: TimeSettings = field(default_factory=TimeSettings)
    notify: NotifySettings = field(default_factory=NotifySettings)


def load_runtime_settings(path: Path) -> RuntimeSettings:
    if not path.exists():
        return RuntimeSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        retention_data = data.get("retention", {})
        auth_data = data.get("auth", {})
        backup_location_data = data.get("backup_location", {})
        time_data = data.get("time", {})
        time_kwargs = {
            k: v for k, v in time_data.items()
            if k in TimeSettings.__dataclass_fields__
        }
        if isinstance(time_kwargs.get("ntp_servers"), list):
            time_kwargs["ntp_servers"] = tuple(time_kwargs["ntp_servers"])
        notify_data = data.get("notify", {})
        notify_kwargs = {
            k: v for k, v in notify_data.items()
            if k in NotifySettings.__dataclass_fields__
        }
        if isinstance(notify_kwargs.get("email_to"), list):
            notify_kwargs["email_to"] = tuple(notify_kwargs["email_to"])
        return RuntimeSettings(
            retention=RetentionSettings(**{
                k: v for k, v in retention_data.items()
                if k in RetentionSettings.__dataclass_fields__
            }),
            auth=AuthSettings(**{
                k: v for k, v in auth_data.items()
                if k in AuthSettings.__dataclass_fields__
            }),
            backup_location=BackupLocationSettings(**{
                k: v for k, v in backup_location_data.items()
                if k in BackupLocationSettings.__dataclass_fields__
            }),
            time=TimeSettings(**time_kwargs),
            notify=NotifySettings(**notify_kwargs),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return RuntimeSettings()


def save_runtime_settings(path: Path, settings: RuntimeSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = asdict(settings)
    if isinstance(serializable.get("time", {}).get("ntp_servers"), tuple):
        serializable["time"]["ntp_servers"] = list(serializable["time"]["ntp_servers"])
    notify = serializable.get("notify", {})
    if isinstance(notify.get("email_to"), tuple):
        notify["email_to"] = list(notify["email_to"])
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
