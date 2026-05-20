from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServiceSetupConfig:
    master_passphrase: str
    admin_username: str
    admin_password: str
    install_path: Path | None = None
    bind_host: str = "127.0.0.1"
    bind_port: int = 8443
    lan_bind_enabled: bool = False
    cert_pfx_path: Path | None = None

    @property
    def service_url(self) -> str:
        return f"https://{self.bind_host}:{self.bind_port}"
