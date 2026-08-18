from __future__ import annotations

import logging.config
import socket

import pytest
import uvicorn

from app_v4.desktop.launcher import (
    SAFE_LOG_CONFIG,
    find_free_port,
    is_initialized,
    probe_host,
    wait_for_port,
)


def test_is_initialized_false_when_envelope_missing(tmp_path):
    base_dir = tmp_path / "ncmv4"
    assert is_initialized(base_dir) is False


def test_is_initialized_true_when_envelope_present(tmp_path):
    base_dir = tmp_path / "ncmv4"
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "master.dpapi").write_bytes(b"opaque")
    assert is_initialized(base_dir) is True


def test_find_free_port_returns_bindable_port():
    port = find_free_port("127.0.0.1")
    assert 1024 < port < 65536
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.close()


def test_wait_for_port_returns_false_when_unreachable():
    free_port = find_free_port("127.0.0.1")
    assert wait_for_port("127.0.0.1", free_port, timeout=0.5) is False


def test_wait_for_port_returns_true_when_listener_open():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        assert wait_for_port("127.0.0.1", port, timeout=2.0) is True
    finally:
        listener.close()


def test_wait_for_port_treats_wildcard_host_as_loopback():
    """Bug: probing wait_for_port('0.0.0.0', port) connects to 0.0.0.0, which
    is not a routable destination on Windows — it always fails to connect even
    though the backend is bound and listening on all interfaces.

    The probe must redirect 0.0.0.0 / :: wildcard binds to 127.0.0.1 / ::1.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("0.0.0.0", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        assert wait_for_port("0.0.0.0", port, timeout=2.0) is True
    finally:
        listener.close()


def test_safe_log_config_loads_without_isatty(monkeypatch):
    """Windowed PyInstaller builds set sys.stdout/stderr to None.

    Default uvicorn LOGGING_CONFIG calls stream.isatty() at formatter init,
    which raises AttributeError on None. SAFE_LOG_CONFIG must avoid that.
    """
    monkeypatch.setattr("sys.stdout", None)
    monkeypatch.setattr("sys.stderr", None)
    logging.config.dictConfig(SAFE_LOG_CONFIG)


def test_safe_log_config_accepted_by_uvicorn():
    config = uvicorn.Config(
        app="app_v4.service.main:create_runtime_app",
        factory=True,
        host="127.0.0.1",
        port=find_free_port(),
        log_config=SAFE_LOG_CONFIG,
    )
    assert config.log_config is SAFE_LOG_CONFIG


@pytest.mark.parametrize(
    "bind_host,expected",
    [
        ("0.0.0.0", "127.0.0.1"),
        ("", "127.0.0.1"),
        ("::", "::1"),
        ("127.0.0.1", "127.0.0.1"),
        ("192.168.10.5", "192.168.10.5"),
    ],
)
def test_probe_host_maps_wildcard_to_loopback(bind_host, expected):
    """Clients (httpx, browser) must not dial 0.0.0.0 — it is not routable."""
    assert probe_host(bind_host) == expected
