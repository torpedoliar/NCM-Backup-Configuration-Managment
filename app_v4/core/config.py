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

    @property
    def database_url(self) -> str:
        db_path = self.base_dir / "data" / "app.db"
        return f"sqlite+aiosqlite:///{db_path.as_posix()}"

    @property
    def service_url(self) -> str:
        return f"https://{self.service_host}:{self.service_port}"
