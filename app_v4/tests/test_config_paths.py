from pathlib import Path

import sys

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


def test_settings_has_no_misleading_https_property(tmp_path: Path):
    """Drop the historical service_url property — the backend runs over
    plaintext loopback http. Callers compose URLs themselves.
    """
    settings = Settings(base_dir=tmp_path)

    assert not hasattr(settings, "service_url")


def test_static_dir_resolves_to_meipass_when_frozen(tmp_path: Path, monkeypatch):
    """Under PyInstaller onedir, static bundle lives in _internal/, not next to exe.

    The spec adds static via datas=[(static_dir, "app_v4/service/static")], which
    PyInstaller places at sys._MEIPASS/app_v4/service/static. resolve_paths()
    must return that location when running frozen, not base_dir/app_v4/...
    """
    bundle_dir = tmp_path / "_internal"
    (bundle_dir / "app_v4" / "service" / "static").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)

    settings = Settings(base_dir=tmp_path)
    paths = resolve_paths(settings)

    assert paths.static_dir == bundle_dir / "app_v4" / "service" / "static"


def test_static_dir_falls_back_to_base_dir_when_not_frozen(tmp_path: Path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    settings = Settings(base_dir=tmp_path)
    paths = resolve_paths(settings)

    assert paths.static_dir == tmp_path / "app_v4" / "service" / "static"


def test_base_dir_defaults_to_exe_dir_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "C:/apps/ncm/ncm-v4-desktop.exe")
    monkeypatch.delenv("NCM_V4_BASE_DIR", raising=False)

    assert Settings().base_dir == Path("C:/apps/ncm")


def test_base_dir_defaults_to_cwd_in_dev_mode(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.delenv("NCM_V4_BASE_DIR", raising=False)

    assert Settings().base_dir == Path.cwd()
