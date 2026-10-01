from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app_v4.net.mikrotik_client import AsyncMikrotikClient


class FakeNonInteractiveConn:
    def __init__(self, export_output: str, sftp_data: bytes | None = None):
        self.export_output = export_output
        self.sftp_data = sftp_data
        self.run_commands: list[str] = []

    async def run(self, command: str, check: bool = False):
        self.run_commands.append(command)
        if command.startswith("/export"):
            return SimpleNamespace(exit_status=0, stderr="", stdout=self.export_output)
        return SimpleNamespace(exit_status=0, stderr="", stdout="")

    def start_sftp_client(self):
        class FakeSftpContext:
            def __init__(self, data: bytes | None):
                self.data = data

            async def __aenter__(self):
                mock_sftp = AsyncMock()
                mock_sftp.exists = AsyncMock(return_value=self.data is not None)

                class FakeFile:
                    def __init__(self, d):
                        self.d = d

                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        pass

                    async def read(self):
                        return self.d

                mock_sftp.open = MagicMock(return_value=FakeFile(self.data))
                return mock_sftp

            async def __aexit__(self, *args):
                pass

        return FakeSftpContext(self.sftp_data)


@pytest.mark.asyncio
async def test_mikrotik_client_fetches_text_and_binary_backup():
    export_sample = "/interface bridge add name=bridge1\n/ip address add address=192.168.88.1/24 interface=bridge1"
    binary_sample = b"\x1f\x8b\x08mikrotik-binary-backup-bytes"

    client = AsyncMikrotikClient("192.168.88.1", 22, "admin", "secret")
    client.conn = FakeNonInteractiveConn(export_sample, sftp_data=binary_sample)

    assert await client.enter_enable_mode([]) is True
    assert await client.disable_paging([]) is True

    text = await client.get_running_config([])

    assert "interface bridge add" in text
    assert client.binary_bytes == binary_sample
    assert any("/system backup save" in cmd for cmd in client.conn.run_commands)
    assert any("file remove" in cmd for cmd in client.conn.run_commands)


@pytest.mark.asyncio
async def test_mikrotik_client_resilient_if_binary_fails():
    export_sample = "/interface ethernet set [ find default-name=ether1 ] comment=WAN"

    client = AsyncMikrotikClient("192.168.88.1", 22, "admin", "secret")
    # SFTP returns None (simulating failure)
    client.conn = FakeNonInteractiveConn(export_sample, sftp_data=None)

    text = await client.get_running_config([])

    assert "comment=WAN" in text
    assert client.binary_bytes is None
