import pytest
from pathlib import Path

from app_v4.core.runtime_settings import (
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
