from __future__ import annotations

import asyncio
import sys

import httpx
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app_v4.desktop.api_client import DesktopApiClient
from app_v4.desktop.auth.login_dialog import LoginDialog
from app_v4.desktop.setup.service_config import ServiceSetupConfig
from app_v4.desktop.setup.wizard import SetupWizard
from app_v4.desktop.shell.main_window import MainWindow

DEFAULT_SERVICE_URL = "http://127.0.0.1:8443"


def _service_unreachable(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url}/api/v1/system/status", timeout=2.0)
    except httpx.HTTPError:
        return True
    return response.status_code >= 500


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


def _service_url_from_config(config: ServiceSetupConfig) -> str:
    return f"http://{config.bind_host}:{config.bind_port}"


def main() -> int:
    app = QApplication(sys.argv)
    base_url = DEFAULT_SERVICE_URL

    if _service_unreachable(base_url):
        wizard = SetupWizard()
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return 0
        config = wizard.collect()
        base_url = _service_url_from_config(config)
        if _service_unreachable(base_url):
            QMessageBox.warning(
                None,
                "Service unreachable",
                f"Service at {base_url} is still unreachable. Start the backend service before continuing.",
            )
            return 0

    token = _run_login(base_url)
    if token is None:
        return 0

    window = MainWindow(service_url=base_url, access_token=token)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
