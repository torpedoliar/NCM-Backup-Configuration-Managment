from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
import traceback
from dataclasses import dataclass
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


@dataclass(frozen=True)
class DesktopMode:
    serve: bool
    host: str | None
    port: int | None


@dataclass(frozen=True)
class ServeRunResult:
    exit_code: int
    message: str


def parse_desktop_args(argv: list[str]) -> DesktopMode:
    """Parse desktop entrypoint arguments.

    Default behavior (no flags) is GUI mode, preserving the legacy entrypoint.
    --serve runs the backend headless, suitable for a Windows scheduled task or
    background service. --host / --port override the persisted bind settings
    only for the headless run.
    """
    parser = argparse.ArgumentParser(prog="ncm-v4-desktop", add_help=True)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run backend headless (no GUI, no login prompt). Used for autostart.",
    )
    parser.add_argument("--host", default=None, help="Override bind host (serve mode).")
    parser.add_argument("--port", type=int, default=None, help="Override bind port (serve mode).")
    args = parser.parse_args(argv)
    return DesktopMode(serve=bool(args.serve), host=args.host, port=args.port)


def _block_until_signal_default() -> None:
    """Block on Ctrl-C / SIGTERM. Used by run_serve in production."""
    import signal
    import threading

    stop_event = threading.Event()

    def _stop(_signum, _frame):
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
    except (ValueError, AttributeError):
        # Some platforms (Windows GUI bundles) reject signal handlers; fall back
        # to a plain wait so the call still blocks until the process is killed.
        pass

    stop_event.wait()


def run_serve(
    mode: DesktopMode,
    base_dir: Path,
    *,
    load_settings,
    is_initialized,
    backend_factory,
    wait_for_port,
    block_until_signal,
) -> ServeRunResult:
    """Headless backend entrypoint used by Windows autostart / scheduled tasks.

    Refuses to start if the install hasn't gone through first-run setup, since
    there is no GUI to drive the wizard. Honours --host / --port overrides for
    the current invocation only (does not persist them).
    """
    if not is_initialized(base_dir):
        return ServeRunResult(
            exit_code=1,
            message=(
                "NCM v4 is not initialized. Run the desktop GUI once to complete first-run setup "
                "before enabling auto-start."
            ),
        )

    settings_file = base_dir / "data" / "service.json"
    persisted = load_settings(settings_file) or ServiceSettings(bind_host="127.0.0.1", bind_port=8443)
    host = mode.host or persisted.bind_host
    port = mode.port or persisted.bind_port

    backend = backend_factory(host=host, port=port)
    backend.start()
    if not wait_for_port(host, port, timeout=30):
        backend.stop()
        return ServeRunResult(
            exit_code=1,
            message=f"Backend did not start on {host}:{port}.",
        )
    try:
        block_until_signal()
        return ServeRunResult(exit_code=0, message="Backend stopped.")
    finally:
        backend.stop()


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


async def _login_and_close(base_url: str, username: str, password: str) -> tuple[str, str] | None:
    client = DesktopApiClient(base_url)
    try:
        await client.login(username, password)
        if client.access_token is None:
            return None
        return client.access_token, client.refresh_token or ""
    finally:
        await client.close()


def _run_login(base_url: str) -> tuple[str, str] | None:
    dialog = LoginDialog()
    while True:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        username, password = dialog.credentials()
        if not username or not password:
            QMessageBox.warning(dialog, "Sign in", "Username and password are required.")
            continue
        try:
            tokens = asyncio.run(_login_and_close(base_url, username, password))
        except httpx.HTTPError as exc:
            QMessageBox.critical(dialog, "Sign in failed", f"Could not authenticate: {exc}")
            continue
        return tokens


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
    mode = parse_desktop_args(sys.argv[1:])
    _ensure_stdio_streams()

    if mode.serve:
        return _run_serve_main(mode)

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
        tokens = _run_login(base_url)
        if tokens is None:
            return 0
        access_token, refresh_token = tokens

        window = MainWindow(
            service_url=base_url,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        window.show()
        return app.exec()
    finally:
        backend.stop()


def _run_serve_main(mode: DesktopMode) -> int:
    base_dir = _resource_base_dir()
    from app_v4.core.logging import configure_file_logger
    configure_file_logger(base_dir / "logs")
    os.environ["NCM_V4_BASE_DIR"] = str(base_dir)

    result = run_serve(
        mode=mode,
        base_dir=base_dir,
        load_settings=load_service_settings,
        is_initialized=is_initialized,
        backend_factory=lambda host, port: BackendThread(host=host, port=port),
        wait_for_port=wait_for_port,
        block_until_signal=_block_until_signal_default,
    )
    if result.exit_code != 0:
        # Stderr is captured by the wrapper or service log; print so logs see it.
        print(result.message, file=sys.stderr)
    return int(result.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
