from __future__ import annotations

import socket
from pathlib import Path

import pytest

from app_v4.desktop import main as desktop_main
from app_v4.desktop.main import PortPrompt
from app_v4.desktop.service_settings import ServiceSettings, load_service_settings
from app_v4.desktop.setup.service_config import ServiceSetupConfig


def _occupy_port() -> tuple[socket.socket, int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    return listener, listener.getsockname()[1]


def test_resolve_bind_settings_uses_setup_config_when_available(tmp_path: Path):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    free_port = sock.getsockname()[1]
    sock.close()
    config = ServiceSetupConfig(
        master_passphrase="x",
        admin_username="admin",
        admin_password="y",
        bind_host="127.0.0.1",
        bind_port=free_port,
    )

    bind = desktop_main._resolve_bind_settings(tmp_path, config)

    assert bind == ServiceSettings(bind_host="127.0.0.1", bind_port=free_port)
    persisted = load_service_settings(tmp_path / "data" / "service.json")
    assert persisted == bind


def test_resolve_bind_settings_loads_from_disk_on_subsequent_runs(tmp_path: Path):
    target = tmp_path / "data" / "service.json"
    target.parent.mkdir(parents=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    free_port = sock.getsockname()[1]
    sock.close()
    target.write_text(f'{{"bind_host":"127.0.0.1","bind_port":{free_port}}}')

    bind = desktop_main._resolve_bind_settings(tmp_path, None)

    assert bind == ServiceSettings(bind_host="127.0.0.1", bind_port=free_port)


def test_resolve_bind_settings_prompts_when_port_in_use(tmp_path: Path):
    listener, busy_port = _occupy_port()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    free_port = sock.getsockname()[1]
    sock.close()

    config = ServiceSetupConfig(
        master_passphrase="x",
        admin_username="admin",
        admin_password="y",
        bind_host="127.0.0.1",
        bind_port=busy_port,
    )

    prompts: list[int] = []

    def fake_prompt(host: str, busy: int, suggested: int) -> int | None:
        prompts.append(suggested)
        return free_port

    try:
        bind = desktop_main._resolve_bind_settings(tmp_path, config, prompt_for_port=fake_prompt)
    finally:
        listener.close()

    assert bind == ServiceSettings(bind_host="127.0.0.1", bind_port=free_port)
    assert prompts == [busy_port + 1]


def test_resolve_bind_settings_returns_none_when_user_cancels(tmp_path: Path):
    listener, busy_port = _occupy_port()
    config = ServiceSetupConfig(
        master_passphrase="x",
        admin_username="admin",
        admin_password="y",
        bind_host="127.0.0.1",
        bind_port=busy_port,
    )

    try:
        bind = desktop_main._resolve_bind_settings(
            tmp_path, config, prompt_for_port=lambda *a, **k: None
        )
    finally:
        listener.close()

    assert bind is None


def test_default_port_prompt_uses_real_qinputdialog_signature(qtbot, monkeypatch):
    """Regression for `QInputDialog.getInt(): unsupported keyword 'min'`.

    PySide6's QInputDialog.getInt does NOT accept min=/max= kwargs (PyQt5 did).
    The default prompt callable must call it correctly. We monkeypatch only the
    last-mile call to capture the positional args, but still go through the real
    PortPrompt.default code path.
    """
    captured: dict = {}

    def fake_get_int(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return 9000, True

    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(fake_get_int))

    result = PortPrompt.default("127.0.0.1", busy_port=8443, suggested=8444)

    assert result == 9000
    assert captured["kwargs"] == {}, "default prompt must use positional args (PySide6 signature)"
    assert len(captured["args"]) >= 4
