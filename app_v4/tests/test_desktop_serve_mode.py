from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app_v4.desktop.main import (
    DesktopMode,
    ServeRunResult,
    parse_desktop_args,
    run_serve,
)
from app_v4.desktop.service_settings import ServiceSettings


def test_parse_default_mode_is_gui():
    mode = parse_desktop_args([])
    assert mode == DesktopMode(serve=False, host=None, port=None)


def test_parse_serve_flag_only_returns_serve_mode_with_defaults():
    mode = parse_desktop_args(["--serve"])
    assert mode == DesktopMode(serve=True, host=None, port=None)


def test_parse_serve_with_host_and_port():
    mode = parse_desktop_args(["--serve", "--host", "0.0.0.0", "--port", "9443"])
    assert mode == DesktopMode(serve=True, host="0.0.0.0", port=9443)


def test_parse_serve_rejects_invalid_port():
    with pytest.raises(SystemExit):
        parse_desktop_args(["--serve", "--port", "not-a-number"])


class FakeBackend:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self, timeout: float = 5.0) -> None:
        self.stopped = True


def test_run_serve_skips_when_not_initialized(tmp_path):
    persisted = ServiceSettings(bind_host="127.0.0.1", bind_port=9000)
    backend_factory = MagicMock(return_value=FakeBackend("127.0.0.1", 9000))
    wait_fn = MagicMock(return_value=True)
    block_fn = MagicMock()

    result = run_serve(
        mode=DesktopMode(serve=True, host=None, port=None),
        base_dir=tmp_path,
        load_settings=lambda _: persisted,
        is_initialized=lambda _: False,
        backend_factory=backend_factory,
        wait_for_port=wait_fn,
        block_until_signal=block_fn,
    )

    assert isinstance(result, ServeRunResult)
    assert result.exit_code == 1
    assert "not initialized" in result.message.lower()
    backend_factory.assert_not_called()
    block_fn.assert_not_called()


def test_run_serve_starts_backend_and_blocks_with_persisted_settings(tmp_path):
    persisted = ServiceSettings(bind_host="127.0.0.1", bind_port=9000)
    fake = FakeBackend("127.0.0.1", 9000)
    backend_factory = MagicMock(return_value=fake)
    wait_fn = MagicMock(return_value=True)
    block_fn = MagicMock()

    result = run_serve(
        mode=DesktopMode(serve=True, host=None, port=None),
        base_dir=tmp_path,
        load_settings=lambda _: persisted,
        is_initialized=lambda _: True,
        backend_factory=backend_factory,
        wait_for_port=wait_fn,
        block_until_signal=block_fn,
    )

    assert result.exit_code == 0
    backend_factory.assert_called_once_with(host="127.0.0.1", port=9000)
    assert fake.started is True
    block_fn.assert_called_once()
    assert fake.stopped is True


def test_run_serve_overrides_host_and_port_from_args(tmp_path):
    persisted = ServiceSettings(bind_host="127.0.0.1", bind_port=8443)
    fake = FakeBackend("0.0.0.0", 9999)
    backend_factory = MagicMock(return_value=fake)

    result = run_serve(
        mode=DesktopMode(serve=True, host="0.0.0.0", port=9999),
        base_dir=tmp_path,
        load_settings=lambda _: persisted,
        is_initialized=lambda _: True,
        backend_factory=backend_factory,
        wait_for_port=lambda host, port, timeout: True,
        block_until_signal=lambda: None,
    )

    assert result.exit_code == 0
    backend_factory.assert_called_once_with(host="0.0.0.0", port=9999)


def test_run_serve_stops_backend_when_port_does_not_open(tmp_path):
    persisted = ServiceSettings(bind_host="127.0.0.1", bind_port=9000)
    fake = FakeBackend("127.0.0.1", 9000)
    backend_factory = MagicMock(return_value=fake)
    block_fn = MagicMock()

    result = run_serve(
        mode=DesktopMode(serve=True, host=None, port=None),
        base_dir=tmp_path,
        load_settings=lambda _: persisted,
        is_initialized=lambda _: True,
        backend_factory=backend_factory,
        wait_for_port=lambda host, port, timeout: False,
        block_until_signal=block_fn,
    )

    assert result.exit_code == 1
    assert "did not start" in result.message.lower()
    assert fake.started is True
    assert fake.stopped is True
    block_fn.assert_not_called()
