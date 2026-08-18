from __future__ import annotations

import socket
from pathlib import Path

import pytest

from app_v4.desktop.service_settings import (
    ServiceSettings,
    is_port_available,
    load_service_settings,
    save_service_settings,
)


def test_save_and_load_round_trip(tmp_path: Path):
    target = tmp_path / "data" / "service.json"
    save_service_settings(target, ServiceSettings(bind_host="127.0.0.1", bind_port=9001))

    loaded = load_service_settings(target)

    assert loaded == ServiceSettings(bind_host="127.0.0.1", bind_port=9001)


def test_load_returns_none_when_file_missing(tmp_path: Path):
    assert load_service_settings(tmp_path / "missing.json") is None


def test_load_returns_none_when_file_corrupt(tmp_path: Path):
    target = tmp_path / "service.json"
    target.write_text("not json")

    assert load_service_settings(target) is None


def test_save_creates_parent_directories(tmp_path: Path):
    target = tmp_path / "deep" / "data" / "service.json"
    save_service_settings(target, ServiceSettings(bind_host="127.0.0.1", bind_port=9100))
    assert target.exists()


def test_is_port_available_returns_true_for_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    free_port = sock.getsockname()[1]
    sock.close()

    assert is_port_available("127.0.0.1", free_port) is True


def test_is_port_available_returns_false_when_listener_open():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        port = listener.getsockname()[1]
        assert is_port_available("127.0.0.1", port) is False
    finally:
        listener.close()
