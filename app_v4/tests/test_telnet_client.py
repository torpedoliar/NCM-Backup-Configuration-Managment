import asyncio

import pytest

from app_v4.net.telnet_client import AsyncTelnetClient


class FakeTelnetWriter:
    def __init__(self):
        self.writes: list[str] = []

    def write(self, text: str) -> None:
        self.writes.append(text)

    def close(self) -> None:
        pass


class FakeTelnetReader:
    def __init__(self, chunks: list[str]):
        self._chunks = list(chunks)

    async def read(self, size: int) -> str:
        if self._chunks:
            return self._chunks.pop(0)
        await asyncio.sleep(0.05)
        return ""


def _make_client(enable_password: str = "") -> AsyncTelnetClient:
    return AsyncTelnetClient("switch", 23, "admin", "test-password-not-real", enable_password=enable_password)


@pytest.mark.asyncio
async def test_telnet_enter_enable_mode_always_sends_enable_command():
    client = _make_client()
    client.reader = FakeTelnetReader(["switch>", "switch#"])
    client.writer = FakeTelnetWriter()

    assert await client.enter_enable_mode(["#"]) is True

    assert client.writer.writes == ["enable\n"]


@pytest.mark.asyncio
async def test_telnet_enter_enable_mode_sends_password_when_prompted():
    client = _make_client(enable_password="enable-secret")
    client.reader = FakeTelnetReader(["Password:", "switch#"])
    client.writer = FakeTelnetWriter()

    assert await client.enter_enable_mode(["#"]) is True

    assert client.writer.writes == ["enable\n", "enable-secret\n"]


@pytest.mark.asyncio
async def test_telnet_get_running_config_detects_generic_more_prompt():
    client = _make_client()
    client.reader = FakeTelnetReader([
        "show running-config\ninterface 1\nPress any key for more...",
        "\ninterface 2\nswitch#",
    ])
    client.writer = FakeTelnetWriter()

    text = await client.get_running_config(["--More--"])

    assert "interface 1" in text
    assert "interface 2" in text
    assert " " in client.writer.writes  # space sent to continue paging
