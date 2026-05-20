# Phase 7 — Wizard Input Validation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Setup wizard rejects weak/invalid input on first run so installs cannot leave easy-to-guess accounts or unusable bind ports.

**Architecture:** Pure desktop change. Pull validation logic into a Qt-free `desktop/setup/validators.py` module (testable without a display), then call it from each `QWizardPage.isComplete()` plus per-field error labels. Add confirmation fields for passphrase and admin password.

**Tech Stack:** PySide6 (QWizard), pytest, Python 3.13.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 7.

---

## Task 1: Pure validators module

**Files:**
- Create: `app_v4/desktop/setup/validators.py`
- Create: `app_v4/tests/test_setup_validators.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from app_v4.desktop.setup.validators import (
    validate_passphrase,
    validate_username,
    validate_password,
    validate_bind_host,
    validate_bind_port,
)


@pytest.mark.parametrize("value,confirm,expected_substring", [
    ("short", "short", "12 characters"),
    ("nouppercaseornumber!", "nouppercaseornumber!", "upper"),
    ("NoDigitsHere!!!", "NoDigitsHere!!!", "digit"),
    ("StrongP4ssphrase", "different", "match"),
    ("StrongP4ssphrase", "StrongP4ssphrase", None),
])
def test_validate_passphrase(value, confirm, expected_substring):
    error = validate_passphrase(value, confirm)
    if expected_substring is None:
        assert error is None
    else:
        assert expected_substring.lower() in (error or "").lower()


@pytest.mark.parametrize("value,expected_substring", [
    ("ab", "3"),
    ("1starts_digit", "letter"),
    ("has space", "alphanumeric"),
    ("admin", None),
    ("ops_admin-1", None),
])
def test_validate_username(value, expected_substring):
    error = validate_username(value)
    if expected_substring is None:
        assert error is None
    else:
        assert expected_substring.lower() in (error or "").lower()


@pytest.mark.parametrize("password,confirm,expected_substring", [
    ("short1A", "short1A", "8"),
    ("alllower1", "alllower1", "upper"),
    ("ALLUPPER1", "ALLUPPER1", "lower"),
    ("NoDigitsXX", "NoDigitsXX", "digit"),
    ("Goodpass1", "different", "match"),
    ("Goodpass1", "Goodpass1", None),
])
def test_validate_password(password, confirm, expected_substring):
    error = validate_password(password, confirm)
    if expected_substring is None:
        assert error is None
    else:
        assert expected_substring.lower() in (error or "").lower()


@pytest.mark.parametrize("value,is_valid", [
    ("127.0.0.1", True),
    ("0.0.0.0", True),
    ("192.168.10.5", True),
    ("999.0.0.1", False),
    ("256.1.1.1", False),
    ("hostname", True),
    ("with space", False),
    ("", False),
])
def test_validate_bind_host(value, is_valid):
    error = validate_bind_host(value)
    if is_valid:
        assert error is None
    else:
        assert error is not None


@pytest.mark.parametrize("value,is_valid", [
    ("8443", True),
    ("1024", True),
    ("65535", True),
    ("1023", False),
    ("65536", False),
    ("0", False),
    ("abc", False),
    ("", False),
])
def test_validate_bind_port(value, is_valid):
    error = validate_bind_port(value)
    if is_valid:
        assert error is None
    else:
        assert error is not None
```

- [ ] **Step 2: Run, FAIL.**

Run: `python -m pytest app_v4/tests/test_setup_validators.py -v`

- [ ] **Step 3: Implement validators**

Create `app_v4/desktop/setup/validators.py`:

```python
from __future__ import annotations

import re

_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-.]*$")


def validate_passphrase(value: str, confirm: str) -> str | None:
    if len(value) < 12:
        return "Passphrase must be at least 12 characters"
    if not re.search(r"[A-Z]", value):
        return "Passphrase must include an upper-case letter"
    if not re.search(r"[a-z]", value):
        return "Passphrase must include a lower-case letter"
    if not re.search(r"\d", value):
        return "Passphrase must include a digit"
    if value != confirm:
        return "Passphrases do not match"
    return None


def validate_username(value: str) -> str | None:
    if len(value) < 3 or len(value) > 64:
        return "Username must be 3 to 64 characters"
    if not _USERNAME_RE.match(value):
        return (
            "Username must start with a letter and contain only "
            "alphanumerics, underscore, or dash"
        )
    return None


def validate_password(value: str, confirm: str) -> str | None:
    if len(value) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", value):
        return "Password must include an upper-case letter"
    if not re.search(r"[a-z]", value):
        return "Password must include a lower-case letter"
    if not re.search(r"\d", value):
        return "Password must include a digit"
    if value != confirm:
        return "Passwords do not match"
    return None


def validate_bind_host(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return "Bind host is required"
    if " " in text:
        return "Bind host must not contain whitespace"
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", text):
        try:
            octets = [int(part) for part in text.split(".")]
        except ValueError:
            return "Bind host octets must be numbers"
        if any(o < 0 or o > 255 for o in octets):
            return "Bind host octets must be between 0 and 255"
        return None
    if not _HOSTNAME_RE.match(text):
        return "Bind host must be an IPv4 address or hostname"
    return None


def validate_bind_port(value: str) -> str | None:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return "Bind port must be a number"
    if port < 1024 or port > 65535:
        return "Bind port must be between 1024 and 65535"
    return None
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/desktop/setup/validators.py app_v4/tests/test_setup_validators.py
git commit -m "feat(wizard): pure validators module"
```

---

## Task 2: Wire validators into wizard pages

**Files:**
- Modify: `app_v4/desktop/setup/wizard.py`
- Modify: `app_v4/tests/test_desktop_setup_config.py`

- [ ] **Step 1: Write failing tests**

Append to `app_v4/tests/test_desktop_setup_config.py`:

```python
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
```

- [ ] **Step 2: Run, FAIL.**

Run: `python -m pytest app_v4/tests/test_desktop_setup_config.py -v`

- [ ] **Step 3: Modify `wizard.py`**

Replace the wizard pages with validator-driven versions:

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from app_v4.desktop.setup.service_config import ServiceSetupConfig
from app_v4.desktop.setup.validators import (
    validate_bind_host,
    validate_bind_port,
    validate_passphrase,
    validate_password,
    validate_username,
)


class _ValidatingPage(QWizardPage):
    def _bind_change(self, *fields: QLineEdit) -> None:
        for field in fields:
            field.textChanged.connect(self._update_error)

    def _update_error(self) -> None:
        error = self._validation_error()
        if hasattr(self, "error_label"):
            self.error_label.setText(error or "")
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._validation_error() is None

    def _validation_error(self) -> str | None:
        raise NotImplementedError


class WelcomePage(_ValidatingPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Welcome")
        self.setSubTitle("Configure the NCM v4 service.")
        layout = QFormLayout(self)
        self.master_passphrase = QLineEdit()
        self.master_passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        self.master_passphrase.setPlaceholderText("Choose a strong passphrase (12+ chars)")
        self.master_passphrase_confirm = QLineEdit()
        self.master_passphrase_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.master_passphrase_confirm.setPlaceholderText("Repeat passphrase")
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        layout.addRow("Master passphrase", self.master_passphrase)
        layout.addRow("Confirm passphrase", self.master_passphrase_confirm)
        layout.addRow("", self.error_label)
        self._bind_change(self.master_passphrase, self.master_passphrase_confirm)

    def _validation_error(self) -> str | None:
        return validate_passphrase(self.master_passphrase.text(), self.master_passphrase_confirm.text())


class ServicePage(_ValidatingPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Service")
        self.setSubTitle("Where the local backend will listen.")
        layout = QFormLayout(self)
        self.bind_host = QLineEdit("127.0.0.1")
        self.bind_port = QLineEdit("8443")
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #ffb800;")
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        layout.addRow("Bind host", self.bind_host)
        layout.addRow("Bind port", self.bind_port)
        layout.addRow("", self.warning_label)
        layout.addRow("", self.error_label)
        self._bind_change(self.bind_host, self.bind_port)

    def _validation_error(self) -> str | None:
        host_error = validate_bind_host(self.bind_host.text())
        if host_error:
            return host_error
        port_error = validate_bind_port(self.bind_port.text())
        if port_error:
            return port_error
        return None

    def _update_error(self) -> None:
        super()._update_error()
        host = self.bind_host.text().strip()
        if host == "0.0.0.0":
            self.warning_label.setText(
                "⚠ Binding to 0.0.0.0 exposes the service to the local network."
            )
        else:
            self.warning_label.setText("")


class AdminPage(_ValidatingPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Admin")
        self.setSubTitle("Initial administrator account.")
        layout = QFormLayout(self)
        self.username = QLineEdit("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_confirm = QLineEdit()
        self.password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        layout.addRow("Admin username", self.username)
        layout.addRow("Admin password", self.password)
        layout.addRow("Confirm password", self.password_confirm)
        layout.addRow("", self.error_label)
        self._bind_change(self.username, self.password, self.password_confirm)

    def _validation_error(self) -> str | None:
        username_error = validate_username(self.username.text())
        if username_error:
            return username_error
        return validate_password(self.password.text(), self.password_confirm.text())


class SetupWizard(QWizard):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NCM v4 Setup")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.welcome_page = WelcomePage()
        self.service_page = ServicePage()
        self.admin_page = AdminPage()
        self.addPage(self.welcome_page)
        self.addPage(self.service_page)
        self.addPage(self.admin_page)
        self.resize(560, 380)

    def collect(self) -> ServiceSetupConfig:
        port_text = self.service_page.bind_port.text().strip()
        try:
            bind_port = int(port_text)
        except ValueError:
            bind_port = 8443
        return ServiceSetupConfig(
            master_passphrase=self.welcome_page.master_passphrase.text(),
            admin_username=self.admin_page.username.text().strip() or "admin",
            admin_password=self.admin_page.password.text(),
            bind_host=self.service_page.bind_host.text().strip() or "127.0.0.1",
            bind_port=bind_port,
        )
```

- [ ] **Step 4: Run, PASS.**

Run: `python -m pytest app_v4/tests/test_desktop_setup_config.py app_v4/tests/test_setup_validators.py -v`

- [ ] **Step 5: Commit**

```bash
git add app_v4/desktop/setup/wizard.py app_v4/tests/test_desktop_setup_config.py
git commit -m "feat(wizard): per-page validators with confirm fields and error labels"
```

---

## Task 3: Verify + bundle

- [ ] Run full backend pytest, full frontend vitest, `npm run build`, `installer/v4/build_app.ps1 -SkipWebBuild`. Each step must succeed.
