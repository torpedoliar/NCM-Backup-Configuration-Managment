from types import SimpleNamespace

import pytest

from app_v4.net.ssh_client import AsyncSshClient


class FakeStdin:
    def __init__(self):
        self.writes: list[str] = []

    def write(self, text: str) -> None:
        self.writes.append(text)


class FakeStdout:
    def __init__(self, chunks: list[str]):
        self.chunks = chunks

    async def read(self, size: int) -> str:
        if self.chunks:
            return self.chunks.pop(0)
        return ""


class FakeProcess:
    def __init__(self, chunks: list[str]):
        self.stdin = FakeStdin()
        self.stdout = FakeStdout(chunks)


class NonInteractiveConn:
    def __init__(self):
        self.run_calls: list[str] = []

    async def run(self, command: str, check: bool = False):
        self.run_calls.append(command)
        return SimpleNamespace(
            exit_status=0,
            stderr="",
            stdout="show running-config\ninterface 1\nMore: <space>\nswitch#",
        )


@pytest.mark.asyncio
async def test_ssh_client_enters_enable_mode_through_interactive_shell():
    client = AsyncSshClient("switch", 22, "admin", "test-password-not-real", "enable-secret")
    client.conn = NonInteractiveConn()
    client.process = FakeProcess(["Password:", "switch#"])

    assert await client.enter_enable_mode(["#"]) is True

    assert client.process.stdin.writes == ["enable\n", "enable-secret\n"]
    assert client.conn.run_calls == []


@pytest.mark.asyncio
async def test_ssh_client_disables_paging_through_interactive_shell():
    client = AsyncSshClient("switch", 22, "admin", "test-password-not-real")
    client.conn = NonInteractiveConn()
    client.process = FakeProcess(["% Invalid input\nswitch#", "switch#"])

    assert await client.disable_paging(["terminal length 0", "no page"]) is True

    assert client.process.stdin.writes == ["terminal length 0\n", "no page\n"]
    assert client.conn.run_calls == []


@pytest.mark.asyncio
async def test_ssh_client_fetches_paginated_config_through_interactive_shell():
    client = AsyncSshClient("switch", 22, "admin", "test-password-not-real")
    client.conn = NonInteractiveConn()
    client.process = FakeProcess([
        "show running-config\ninterface 1\nMore: <space>",
        "\ninterface 2\ninterface 3\nswitch#",
    ])

    text = await client.get_running_config(["More: <space>"])

    assert text == "interface 1\ninterface 2\ninterface 3"
    assert client.process.stdin.writes == ["show running-config\n", " "]
    assert client.conn.run_calls == []


@pytest.mark.asyncio
async def test_ssh_client_paging_indicator_at_prompt_line_does_not_break_early():
    client = AsyncSshClient("switch", 22, "admin", "test-password-not-real")
    client.conn = NonInteractiveConn()
    client.process = FakeProcess([
        "show running-config\ninterface 1\nswitch#--More--",
        "\ninterface 2\nswitch#",
    ])

    text = await client.get_running_config(["--More--"])

    assert "interface 1" in text
    assert "interface 2" in text
    assert " " in client.process.stdin.writes
