from __future__ import annotations

import json
import socket
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServiceSettings:
    bind_host: str
    bind_port: int


def save_service_settings(path: Path, settings: ServiceSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


def load_service_settings(path: Path) -> ServiceSettings | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ServiceSettings(bind_host=str(data["bind_host"]), bind_port=int(data["bind_port"]))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def is_port_available(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()
