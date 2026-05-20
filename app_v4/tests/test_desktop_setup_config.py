from app_v4.desktop.setup.service_config import ServiceSetupConfig


def test_service_setup_config_defaults_to_loopback():
    config = ServiceSetupConfig(master_passphrase="secret", admin_username="admin", admin_password="passphrase")

    assert config.bind_host == "127.0.0.1"
    assert config.bind_port == 8443
    assert config.service_url == "https://127.0.0.1:8443"
