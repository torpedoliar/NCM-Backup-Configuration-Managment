import pytest
from pathlib import Path

from app_v4.core.runtime_settings import (
    AuthSettings,
    BackupLocationSettings,
    RetentionSettings,
    RuntimeSettings,
    load_runtime_settings,
    save_runtime_settings,
)


def test_load_returns_defaults_when_file_missing(tmp_path: Path):
    rs = load_runtime_settings(tmp_path / "missing.json")
    assert rs.retention.backup_min_keep == 1
    assert rs.retention.backup_retention_days == 365
    assert rs.retention.audit_retention_days == 90
    assert rs.retention.retention_hour == 3
    assert rs.retention.retention_minute == 0


def test_save_and_load_round_trip(tmp_path: Path):
    target = tmp_path / "data" / "runtime_settings.json"
    rs = RuntimeSettings(
        retention=RetentionSettings(
            backup_min_keep=2, backup_retention_days=30,
            audit_retention_days=60, retention_hour=4, retention_minute=15,
        ),
    )
    save_runtime_settings(target, rs)
    loaded = load_runtime_settings(target)
    assert loaded == rs


def test_load_returns_defaults_when_file_corrupt(tmp_path: Path):
    target = tmp_path / "rs.json"
    target.write_text("not json")
    rs = load_runtime_settings(target)
    assert rs.retention.backup_min_keep == 1


def test_save_creates_parent_directories(tmp_path: Path):
    target = tmp_path / "deep" / "data" / "runtime_settings.json"
    save_runtime_settings(target, RuntimeSettings())
    assert target.exists()


def test_auth_defaults():
    rs = RuntimeSettings()
    assert rs.auth.access_token_minutes == 15
    assert rs.auth.refresh_token_days == 7
    assert rs.auth.lockout_threshold == 5
    assert rs.auth.lockout_window_minutes == 10
    assert rs.auth.lockout_duration_minutes == 30
    assert rs.auth.password_min_length == 8
    assert rs.auth.password_require_upper is True
    assert rs.auth.password_require_lower is True
    assert rs.auth.password_require_digit is True
    assert rs.auth.password_require_symbol is False


def test_save_load_round_trip_includes_auth(tmp_path: Path):
    target = tmp_path / "rs.json"
    rs = RuntimeSettings(
        retention=RetentionSettings(),
        auth=AuthSettings(access_token_minutes=30, lockout_threshold=0),
    )
    save_runtime_settings(target, rs)
    loaded = load_runtime_settings(target)
    assert loaded.auth.access_token_minutes == 30
    assert loaded.auth.lockout_threshold == 0


def test_backup_location_defaults_to_config_value():
    rs = RuntimeSettings()
    assert rs.backup_location.backup_root_folder is None


def test_save_load_round_trip_includes_backup_location(tmp_path: Path):
    target = tmp_path / "rs.json"
    rs = RuntimeSettings(backup_location=BackupLocationSettings(backup_root_folder="D:/Backups/NCM"))
    save_runtime_settings(target, rs)
    loaded = load_runtime_settings(target)
    assert loaded.backup_location.backup_root_folder == "D:/Backups/NCM"
