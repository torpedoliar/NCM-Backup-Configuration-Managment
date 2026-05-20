from app_v4.desktop.setup.service_config import ServiceSetupConfig
from app_v4.desktop.setup.wizard import SetupWizard


def test_service_setup_config_defaults_to_loopback():
    config = ServiceSetupConfig(master_passphrase="secret", admin_username="admin", admin_password="passphrase")

    assert config.bind_host == "127.0.0.1"
    assert config.bind_port == 8443
    assert config.service_url == "https://127.0.0.1:8443"


def test_setup_wizard_collect_returns_typed_config(qtbot):
    wizard = SetupWizard()
    qtbot.addWidget(wizard)
    wizard.service_page.bind_host.setText("192.168.10.5")
    wizard.service_page.bind_port.setText("9443")
    wizard.admin_page.username.setText("opadmin")
    wizard.admin_page.password.setText("S3cret!Pass")
    wizard.welcome_page.master_passphrase.setText("master-pass")

    config = wizard.collect()

    assert config.bind_host == "192.168.10.5"
    assert config.bind_port == 9443
    assert config.admin_username == "opadmin"
    assert config.admin_password == "S3cret!Pass"
    assert config.master_passphrase == "master-pass"
    assert config.service_url == "https://192.168.10.5:9443"
