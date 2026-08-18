from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app_v4.desktop.autostart import (
    AutostartConfig,
    AutostartStatus,
    SCHTASKS_TASK_NAME,
    build_create_command,
    build_delete_command,
    build_query_command,
    parse_query_output,
)


def test_query_command_uses_named_task():
    cmd = build_query_command()
    assert cmd[0].lower().endswith("schtasks") or cmd[0].lower().endswith("schtasks.exe")
    assert "/Query" in cmd
    assert "/TN" in cmd
    assert SCHTASKS_TASK_NAME in cmd


def test_delete_command_force_removes_named_task():
    cmd = build_delete_command()
    assert "/Delete" in cmd
    assert "/TN" in cmd
    assert SCHTASKS_TASK_NAME in cmd
    assert "/F" in cmd


def test_create_command_runs_serve_at_logon_with_highest_priv():
    config = AutostartConfig(
        executable=Path(r"D:\app\ncm-v4-desktop.exe"),
        run_at_startup=True,
        run_at_logon=False,
    )
    cmd = build_create_command(config)
    assert "/Create" in cmd
    assert "/TN" in cmd
    assert SCHTASKS_TASK_NAME in cmd
    assert "/SC" in cmd
    sc_index = cmd.index("/SC")
    assert cmd[sc_index + 1].upper() == "ONSTART"
    tr_index = cmd.index("/TR")
    tr_value = cmd[tr_index + 1]
    # Must invoke our exe with --serve and quote a path that contains spaces
    assert "--serve" in tr_value
    assert "ncm-v4-desktop.exe" in tr_value
    assert "/RL" in cmd
    rl_value = cmd[cmd.index("/RL") + 1]
    assert rl_value.upper() == "HIGHEST"
    assert "/F" in cmd


def test_create_command_uses_logon_trigger_when_requested():
    config = AutostartConfig(
        executable=Path(r"D:\app\ncm-v4-desktop.exe"),
        run_at_startup=False,
        run_at_logon=True,
    )
    cmd = build_create_command(config)
    sc_index = cmd.index("/SC")
    assert cmd[sc_index + 1].upper() == "ONLOGON"


def test_create_config_requires_at_least_one_trigger():
    with pytest.raises(ValueError):
        AutostartConfig(
            executable=Path("ncm-v4-desktop.exe"),
            run_at_startup=False,
            run_at_logon=False,
        )


def test_parse_query_output_returns_disabled_when_task_missing():
    output = (
        "ERROR: The system cannot find the file specified.\r\n"
    )
    status = parse_query_output(returncode=1, stdout="", stderr=output)
    assert status == AutostartStatus(installed=False, ready=False, raw_status=None)


def test_parse_query_output_returns_ready_when_task_present_and_ready():
    output = (
        "Folder: \\\r\n"
        "TaskName       Next Run Time          Status\r\n"
        "============== ====================== ==========\r\n"
        "NCM v4 Backend N/A                    Ready\r\n"
    )
    status = parse_query_output(returncode=0, stdout=output, stderr="")
    assert status.installed is True
    assert status.ready is True
    assert status.raw_status == "Ready"


def test_parse_query_output_returns_installed_but_not_ready_when_disabled():
    output = (
        "TaskName       Next Run Time          Status\r\n"
        "NCM v4 Backend N/A                    Disabled\r\n"
    )
    status = parse_query_output(returncode=0, stdout=output, stderr="")
    assert status.installed is True
    assert status.ready is False
    assert status.raw_status == "Disabled"


def test_create_command_runkey_uses_reg_add():
    config = AutostartConfig(
        executable=Path(r"D:\app\ncm-v4-desktop.exe"),
        run_at_startup=True,
        method="runkey",
    )
    cmd = build_create_command(config)
    assert cmd[0].lower() == "reg"
    assert "add" in cmd
    assert "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" in cmd
    assert "--serve" in cmd[cmd.index("/d") + 1]


def test_query_and_delete_commands_runkey_use_reg():
    assert "reg" in build_query_command(method="runkey")
    assert "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" in build_query_command(method="runkey")
    assert "delete" in build_delete_command(method="runkey")


def test_parse_query_output_runkey_installed_when_value_present():
    status = parse_query_output(returncode=0, stdout="value", stderr="", method="runkey")
    assert status.installed is True
    assert status.ready is True


def test_parse_query_output_runkey_missing_when_reg_fails():
    status = parse_query_output(returncode=1, stdout="", stderr="ERROR", method="runkey")
    assert status.installed is False


def test_create_command_run_whether_logged_on_adds_credentials():
    config = AutostartConfig(
        executable=Path(r"D:\app\ncm-v4-desktop.exe"),
        run_at_startup=True,
        run_whether_logged_on=True,
        username=r"TESTDOMAIN\svc-ncm",
        password="test-password-not-real",
    )
    cmd = build_create_command(config)
    assert "/RU" in cmd
    assert cmd[cmd.index("/RU") + 1] == r"TESTDOMAIN\svc-ncm"
    assert cmd[cmd.index("/RP") + 1] == "secret"


def test_create_config_requires_credentials_when_running_without_logon():
    with pytest.raises(ValueError):
        AutostartConfig(
            executable=Path("ncm-v4-desktop.exe"),
            run_at_startup=True,
            run_whether_logged_on=True,
        )
