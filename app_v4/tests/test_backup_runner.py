import pytest

from app_v4.core.config import Settings
from app_v4.net.runner import BackupRunner, BackupRunResult


class FakeClient:
    def __init__(self, output: str):
        self.output = output
        self.disconnected = False

    async def connect(self):
        return True

    async def enter_enable_mode(self, prompts):
        return True

    async def disable_paging(self, commands):
        return True

    async def get_running_config(self, paging_indicators):
        return self.output

    async def disconnect(self):
        self.disconnected = True


@pytest.mark.asyncio
async def test_backup_runner_normalizes_success_output():
    runner = BackupRunner(
        settings=Settings(network_max_retries=1),
        client_factory=lambda **kwargs: FakeClient("\r\nline1   \r\nline2\r\n"),
    )

    result = await runner.execute_backup(
        protocol="ssh",
        host="10.0.0.1",
        port=22,
        username="admin",
        password="secret",
        enable_password="enable",
    )

    assert result == BackupRunResult(success=True, config_text="line1\nline2", message="Backup completed successfully")


@pytest.mark.asyncio
async def test_backup_runner_rejects_unsupported_protocol():
    runner = BackupRunner(settings=Settings(), client_factory=lambda **kwargs: FakeClient("x"))

    result = await runner.execute_backup("snmp", "host", 161, "u", "p")

    assert result.success is False
    assert "Unsupported protocol" in result.message


@pytest.mark.asyncio
async def test_backup_runner_categorizes_authentication_error():
    class AuthFailClient(FakeClient):
        async def connect(self):
            raise PermissionError("authentication failed")

    runner = BackupRunner(settings=Settings(network_max_retries=1), client_factory=lambda **kwargs: AuthFailClient(""))
    result = await runner.execute_backup("ssh", "host", 22, "u", "p")

    assert result.success is False
    assert result.error_code == "AUTHENTICATION_ERROR"


@pytest.mark.asyncio
async def test_backup_runner_returns_failure_after_retries():
    attempts = 0

    class FailingClient(FakeClient):
        async def connect(self):
            nonlocal attempts
            attempts += 1
            raise ConnectionError("boom")

    runner = BackupRunner(
        settings=Settings(network_max_retries=2, network_retry_delay=0),
        client_factory=lambda **kwargs: FailingClient(""),
    )

    result = await runner.execute_backup("ssh", "host", 22, "u", "p")

    assert attempts == 2
    assert result.success is False
    assert "boom" in result.message


@pytest.mark.asyncio
async def test_backup_runner_accepts_websmart_protocol_from_client_factory():
    created = {}

    def factory(**kwargs):
        created.update(kwargs)
        return FakeClient("websmart config")

    runner = BackupRunner(
        settings=Settings(network_max_retries=1),
        client_factory=factory,
    )

    result = await runner.execute_backup("websmart", "10.0.0.10", 80, "admin", "secret")

    assert result.success is True
    assert result.config_text == "websmart config"
    assert created["protocol"] == "websmart"
    assert created["host"] == "10.0.0.10"
    assert created["port"] == 80
