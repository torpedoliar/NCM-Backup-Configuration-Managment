from __future__ import annotations

import asyncio
import io
import os
import sys
import traceback
from pathlib import Path
from typing import Callable

import httpx
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox

from app_v4.cli import init_command
from app_v4.core.config import Settings
from app_v4.desktop.api_client import DesktopApiClient
from app_v4.desktop.auth.login_dialog import LoginDialog
from app_v4.desktop.launcher import BackendThread, is_initialized, probe_host, wait_for_port
from app_v4.desktop.service_settings import (
    ServiceSettings,
    is_port_available,
    load_service_settings,
    save_service_settings,
)
from app_v4.desktop.setup.service_config import ServiceSetupConfig
from app_v4.desktop.setup.wizard import SetupWizard
from app_v4.desktop.shell.main_window import MainWindow
from app_v4.desktop.theme import load_theme_qss


PromptForPort = Callable[[str, int, int], "int | None"]


class PortPrompt:
    """Wraps QInputDialog.getInt with the correct PySide6 positional signature.

    PySide6's QInputDialog.getInt does NOT accept min=/max= kwargs (PyQt5 did).
    Calling with kwargs raises 'unsupported keyword' at runtime.
    """

    @staticmethod
    def default(host: str, busy_port: int, suggested: int) -> int | None:
        title = "Port in use"
        label = (
            f"Port {busy_port} on {host} is already in use by another process.\n\n"
            "Enter a different port:"
        )
        new_port, accepted = QInputDialog.getInt(
            None, title, label, suggested, 1024, 65535, 1
        )
        if not accepted:
            return None
        return int(new_port)


def _ensure_stdio_streams() -> None:
    """Replace None stdio streams with a no-op buffer.

    PyInstaller windowed builds (--noconsole) set sys.stdout/sys.stderr to None,
    which breaks any library that introspects the stream (e.g. uvicorn's
    DefaultFormatter calling stream.isatty()).
    """
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()


def _resource_base_dir() -> Path:
    """Return the base directory for runtime data (data/, backups/, logs/).

    When running from a PyInstaller bundle, sys.frozen is set; we use the directory
    next to the executable so user state lives outside the temp extraction folder.
    Otherwise we use the current working directory (dev mode).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


async def _run_first_run_init(config: ServiceSetupConfig, settings: Settings) -> None:
    await init_command(
        settings=settings,
        master_passphrase=config.master_passphrase,
        admin_username=config.admin_username,
        admin_password=config.admin_password,
    )


async def _login_and_close(base_url: str, username: str, password: str) -> str | None:
    client = DesktopApiClient(base_url)
    try:
        await client.login(username, password)
        return client.access_token
    finally:
        await client.close()


def _run_login(base_url: str) -> str | None:
    dialog = LoginDialog()
    while True:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        username, password = dialog.credentials()
        if not username or not password:
            QMessageBox.warning(dialog, "Sign in", "Username and password are required.")
            continue
        try:
            token = asyncio.run(_login_and_close(base_url, username, password))
        except httpx.HTTPError as exc:
            QMessageBox.critical(dialog, "Sign in failed", f"Could not authenticate: {exc}")
            continue
        return token


def _ensure_initialized(base_dir: Path, settings: Settings) -> ServiceSetupConfig | None:
    if is_initialized(base_dir):
        return None
    wizard = SetupWizard()
    if wizard.exec() != QDialog.DialogCode.Accepted:
        return None
    config = wizard.collect()
    if not config.master_passphrase or not config.admin_password:
        QMessageBox.warning(None, "Setup", "Master passphrase and admin password are required.")
        return None
    try:
        asyncio.run(_run_first_run_init(config, settings))
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(None, "Setup failed", f"Could not initialize: {exc}\n\n{traceback.format_exc()}")
        return None
    return config


def _resolve_bind_settings(
    base_dir: Path,
    setup_config: ServiceSetupConfig | None,
    prompt_for_port: "PromptForPort | None" = None,
) -> ServiceSettings | None:
    """Resolve persisted bind settings, prompting on conflict.

    Order of precedence:
      1. Setup wizard config (first-run) — saved to data/service.json
      2. data/service.json (subsequent runs) — re-validated
      3. Cancel → None (caller exits cleanly)

    On port conflict the user is shown which port is occupied and asked for
    an alternative. Cancelling aborts startup.
    """
    settings_file = base_dir / "data" / "service.json"
    prompt = prompt_for_port or PortPrompt.default

    if setup_config is not None:
        candidate = ServiceSettings(bind_host=setup_config.bind_host, bind_port=setup_config.bind_port)
    else:
        candidate = load_service_settings(settings_file) or ServiceSettings(
            bind_host="127.0.0.1", bind_port=8443
        )

    while True:
        if is_port_available(candidate.bind_host, candidate.bind_port):
            save_service_settings(settings_file, candidate)
            return candidate

        new_port = prompt(candidate.bind_host, candidate.bind_port, candidate.bind_port + 1)
        if new_port is None:
            return None
        candidate = ServiceSettings(bind_host=candidate.bind_host, bind_port=int(new_port))


def main() -> int:
    _ensure_stdio_streams()
    QCoreApplication.setOrganizationName("NCM")
    QCoreApplication.setApplicationName("NCM v4 Ops Terminal")
    app = QApplication(sys.argv)
    app.setStyleSheet(load_theme_qss())

    base_dir = _resource_base_dir()
    from app_v4.core.logging import configure_file_logger
    configure_file_logger(base_dir / "logs")
    os.environ["NCM_V4_BASE_DIR"] = str(base_dir)
    settings = Settings(base_dir=base_dir)

    setup_config = _ensure_initialized(base_dir, settings)
    if not is_initialized(base_dir):
        QMessageBox.warning(None, "Setup", "Setup was cancelled. NCM v4 cannot start without initialization.")
        return 0

    bind = _resolve_bind_settings(base_dir, setup_config)
    if bind is None:
        return 0

    backend = BackendThread(host=bind.bind_host, port=bind.bind_port)
    backend.start()
    if not wait_for_port(bind.bind_host, bind.bind_port, timeout=30):
        backend.stop()
        QMessageBox.critical(
            None,
            "Backend",
            (
                f"Backend service did not start on {bind.bind_host}:{bind.bind_port}.\n"
                "Check the data/ folder is writable and no antivirus is blocking the bundled exe."
            ),
        )
        return 1

    base_url = f"http://{probe_host(bind.bind_host)}:{bind.bind_port}"
    try:
        token = _run_login(base_url)
        if token is None:
            return 0

        window = MainWindow(service_url=base_url, access_token=token)
        window.show()
        return app.exec()
    finally:
        backend.stop()


if __name__ == "__main__":
    raise SystemExit(main())
