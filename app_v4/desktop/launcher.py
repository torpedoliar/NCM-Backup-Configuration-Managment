from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn


def _safe_log_file_path() -> str:
    base = os.environ.get("NCM_V4_BASE_DIR")
    logs_dir = (Path(base) / "logs") if base else (Path.cwd() / "logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    return str(logs_dir / "ncm-v4.log")


SAFE_LOG_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
        "access":  {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "default": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": _safe_log_file_path(),
            "maxBytes": 10485760,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "default",
        },
        "access": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": _safe_log_file_path(),
            "maxBytes": 10485760,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "access",
        },
    },
    "loggers": {
        "uvicorn":         {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error":   {"level": "INFO"},
        "uvicorn.access":  {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}


def _stdio_streams_available() -> bool:
    """Return True when both sys.stdout and sys.stderr are real streams.

    Why: PyInstaller windowed builds set sys.stdout/sys.stderr to None, which
    breaks uvicorn's default colourised formatter (calls stream.isatty()).
    """
    return sys.stdout is not None and sys.stderr is not None


def is_initialized(base_dir: Path) -> bool:
    return (Path(base_dir) / "data" / "master.dpapi").exists()


def find_free_port(host: str = "127.0.0.1") -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def wait_for_port(host: str, port: int, timeout: float = 30.0, interval: float = 0.2) -> bool:
    probe = probe_host(host)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            sock.connect((probe, port))
            return True
        except OSError:
            time.sleep(interval)
        finally:
            sock.close()
    return False


def probe_host(host: str) -> str:
    """Map wildcard bind hosts to a routable loopback for client connections.

    A backend bound to 0.0.0.0 listens on every interface but the address
    itself is not connectable on Windows; clients (httpx, browser, socket
    probes) must dial 127.0.0.1 to reach it.
    """
    if host in ("0.0.0.0", ""):
        return "127.0.0.1"
    if host == "::":
        return "::1"
    return host


class BackendThread:
    """Run uvicorn in a background thread tied to the desktop process."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        from app_v4.service.main import uvicorn_kwargs
        from app_v4.core.config import Settings

        settings = Settings(service_host=self.host, service_port=self.port)
        kwargs = uvicorn_kwargs(settings)
        kwargs["host"] = self.host
        kwargs["port"] = self.port
        if not _stdio_streams_available():
            kwargs["log_config"] = SAFE_LOG_CONFIG
        config = uvicorn.Config(**kwargs)
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True, name="ncm-v4-backend")
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._server = None
        self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
