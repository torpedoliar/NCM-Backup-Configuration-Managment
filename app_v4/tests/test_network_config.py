from pathlib import Path

from app_v4.core.config import Settings
from app_v4.core.network_config import NetworkConfig, load_network_config
from app_v4.core.paths import resolve_paths


def test_settings_include_backup_and_network_defaults(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)

    assert settings.backup_min_keep == 1
    assert settings.backup_retention_days == 365
    assert settings.network_max_retries == 3
    assert settings.network_connect_timeout == 15
    assert settings.network_retry_delay == 2
    assert settings.network_backoff_multiplier == 2


def test_resolve_paths_includes_scheduler_lock(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    paths = resolve_paths(settings)

    assert paths.scheduler_lock_file == tmp_path / "data" / "scheduler.lock"


def test_load_network_config_from_settings(tmp_path: Path):
    settings = Settings(base_dir=tmp_path, network_max_retries=5)
    config = load_network_config(settings)

    assert isinstance(config, NetworkConfig)
    assert config.max_retries == 5
    assert "terminal length 0" in config.paging_disable_commands
    assert "--More--" in config.paging_indicators
    assert "#" in config.prompts
