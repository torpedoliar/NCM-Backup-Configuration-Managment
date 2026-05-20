from app_v4.desktop.setup.service_config import ServiceSetupConfig
from app_v4.desktop.setup.wizard import SetupWizard


def test_service_setup_config_defaults_to_loopback():
    config = ServiceSetupConfig(master_passphrase="secret", admin_username="admin", admin_password="passphrase")

    assert config.bind_host == "127.0.0.1"
    assert config.bind_port == 8443


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


def test_service_setup_config_has_no_misleading_https_property():
    """The legacy service_url property always returned https://, but the desktop
    backend runs over plaintext loopback http. Removing it forces callers to
    compose URLs from bind_host/bind_port explicitly with the correct scheme.
    """
    config = ServiceSetupConfig(master_passphrase="x", admin_username="admin", admin_password="y")

    assert not hasattr(config, "service_url")


def test_welcome_page_incomplete_when_passphrase_invalid(qtbot):
    wizard = SetupWizard()
    qtbot.addWidget(wizard)
    page = wizard.welcome_page
    page.master_passphrase.setText("short")
    page.master_passphrase_confirm.setText("short")
    assert page.isComplete() is False


def test_welcome_page_complete_when_passphrase_strong(qtbot):
    wizard = SetupWizard()
    qtbot.addWidget(wizard)
    page = wizard.welcome_page
    page.master_passphrase.setText("StrongP4ssphrase")
    page.master_passphrase_confirm.setText("StrongP4ssphrase")
    assert page.isComplete() is True


def test_service_page_incomplete_for_invalid_port(qtbot):
    wizard = SetupWizard()
    qtbot.addWidget(wizard)
    wizard.service_page.bind_host.setText("127.0.0.1")
    wizard.service_page.bind_port.setText("0")
    assert wizard.service_page.isComplete() is False


def test_admin_page_incomplete_when_password_mismatch(qtbot):
    wizard = SetupWizard()
    qtbot.addWidget(wizard)
    wizard.admin_page.username.setText("admin")
    wizard.admin_page.password.setText("Goodpass1")
    wizard.admin_page.password_confirm.setText("Different1")
    assert wizard.admin_page.isComplete() is False
