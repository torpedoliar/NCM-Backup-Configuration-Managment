from pathlib import Path

from app_v4.core.config import Settings
from app_v4.core.paths import resolve_paths


def test_settings_defaults_to_local_backend_bind(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)

    assert settings.service_host == "127.0.0.1"
    assert settings.service_port == 8443
    assert settings.database_url.endswith("/data/app.db")


def test_resolve_paths_creates_expected_locations(tmp_path: Path):
    settings = Settings(base_dir=tmp_path)
    paths = resolve_paths(settings)

    assert paths.base_dir == tmp_path
    assert paths.data_dir == tmp_path / "data"
    assert paths.logs_dir == tmp_path / "logs"
    assert paths.backups_dir == tmp_path / "backups"
    assert paths.static_dir == tmp_path / "app_v4" / "service" / "static"
    assert paths.master_envelope_file == tmp_path / "data" / "master.dpapi"
