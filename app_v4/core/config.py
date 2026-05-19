from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NCM_V4_", extra="ignore")

    base_dir: Path = Field(default_factory=lambda: Path.cwd())
    service_host: str = "127.0.0.1"
    service_port: int = 8443
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 7
    scheduler_lock_seconds: int = 180

    backup_min_keep: int = 1
    backup_retention_days: int = 365
    backup_root_folder: str = "backups"
    diff_context_lines: int = 3

    network_max_retries: int = 3
    network_retry_delay: int = 2
    network_backoff_multiplier: int = 2
    network_connect_timeout: int = 15
    network_command_timeout: int = 60
    network_read_timeout: int = 30

    @property
    def database_url(self) -> str:
        db_path = self.base_dir / "data" / "app.db"
        return f"sqlite+aiosqlite:///{db_path.as_posix()}"

    @property
    def service_url(self) -> str:
        return f"https://{self.service_host}:{self.service_port}"
