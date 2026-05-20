# NCM v4 Phase 6 Desktop Shell and Setup Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the PySide6 desktop application shell, API client, login flow, and first-run setup wizard foundation.

**Architecture:** Desktop app is a native Qt shell that talks to the local FastAPI service. This phase avoids migrating every desktop view; it builds startup, setup, auth, sidebar/topbar chrome, and a dashboard WebEngine placeholder so Phase 7 can add operational views.

**Tech Stack:** PySide6, QWebEngineView, httpx, pytest, pytest-qt.

---

## File Structure

- Modify: `app_v4/requirements-v4.txt` — add PySide6 and pytest-qt.
- Create: `app_v4/desktop/__init__.py`
- Create: `app_v4/desktop/main.py`
- Create: `app_v4/desktop/api_client.py`
- Create: `app_v4/desktop/shell/main_window.py`
- Create: `app_v4/desktop/shell/sidebar.py`
- Create: `app_v4/desktop/shell/topbar.py`
- Create: `app_v4/desktop/setup/wizard.py`
- Create: `app_v4/desktop/setup/service_config.py`
- Create: `app_v4/desktop/theme/ops_terminal.qss`
- Test: `app_v4/tests/test_desktop_api_client.py`
- Test: `app_v4/tests/test_desktop_setup_config.py`
- Test: `app_v4/tests/test_desktop_shell.py`

### Task 1: Desktop Dependencies and API Client

**Files:**
- Modify: `app_v4/requirements-v4.txt`
- Create: `app_v4/desktop/__init__.py`
- Create: `app_v4/desktop/api_client.py`
- Test: `app_v4/tests/test_desktop_api_client.py`

- [ ] **Step 1: Add dependencies**

Append to `app_v4/requirements-v4.txt`:

```text
PySide6>=6.7.0
pytest-qt>=4.4.0
```

Install:

```powershell
rtk python -m pip install -r app_v4/requirements-v4.txt
```

- [ ] **Step 2: Write failing API client test**

Create `app_v4/tests/test_desktop_api_client.py`:

```python
import httpx
import pytest

from app_v4.desktop.api_client import DesktopApiClient


@pytest.mark.asyncio
async def test_desktop_api_client_login_sets_tokens():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/login"
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r", "token_type": "bearer"})

    client = DesktopApiClient("http://127.0.0.1:8443", transport=httpx.MockTransport(handler))
    await client.login("admin", "secret")

    assert client.access_token == "a"
    assert client.refresh_token == "r"
```

- [ ] **Step 3: Create API client**

Create `app_v4/desktop/__init__.py`:

```python
"""NCM v4 desktop client."""
```

Create `app_v4/desktop/api_client.py`:

```python
from __future__ import annotations

import httpx


class DesktopApiClient:
    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.client = httpx.AsyncClient(base_url=self.base_url, transport=transport, timeout=15)

    async def login(self, username: str, password: str) -> None:
        response = await self.client.post("/api/v1/auth/login", json={"username": username, "password": password})
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.client.headers["Authorization"] = f"Bearer {self.access_token}"

    async def system_status(self) -> dict:
        response = await self.client.get("/api/v1/system/status")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()
```

- [ ] **Step 4: Run API client test**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_api_client.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
rtk git add app_v4/requirements-v4.txt app_v4/desktop app_v4/tests/test_desktop_api_client.py
rtk git commit -m "feat: add v4 desktop API client"
```

### Task 2: Service Setup Configuration Model

**Files:**
- Create: `app_v4/desktop/setup/service_config.py`
- Test: `app_v4/tests/test_desktop_setup_config.py`

- [ ] **Step 1: Write failing setup config test**

Create `app_v4/tests/test_desktop_setup_config.py`:

```python
from app_v4.desktop.setup.service_config import ServiceSetupConfig


def test_service_setup_config_defaults_to_loopback():
    config = ServiceSetupConfig(master_passphrase="secret", admin_username="admin", admin_password="passphrase")

    assert config.bind_host == "127.0.0.1"
    assert config.bind_port == 8443
    assert config.service_url == "https://127.0.0.1:8443"
```

- [ ] **Step 2: Create setup model**

Create `app_v4/desktop/setup/service_config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServiceSetupConfig:
    master_passphrase: str
    admin_username: str
    admin_password: str
    install_path: Path | None = None
    bind_host: str = "127.0.0.1"
    bind_port: int = 8443
    lan_bind_enabled: bool = False
    cert_pfx_path: Path | None = None

    @property
    def service_url(self) -> str:
        return f"https://{self.bind_host}:{self.bind_port}"
```

- [ ] **Step 3: Run test**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_setup_config.py -v
```

Expected: pass.

### Task 3: Qt Shell Chrome

**Files:**
- Create: `app_v4/desktop/shell/main_window.py`
- Create: `app_v4/desktop/shell/sidebar.py`
- Create: `app_v4/desktop/shell/topbar.py`
- Create: `app_v4/desktop/theme/ops_terminal.qss`
- Test: `app_v4/tests/test_desktop_shell.py`

- [ ] **Step 1: Write shell test**

Create `app_v4/tests/test_desktop_shell.py`:

```python
import pytest

from app_v4.desktop.shell.main_window import MainWindow


@pytest.mark.qt
async def test_main_window_renders_ops_terminal_chrome(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "NCM v4 Ops Terminal"
    assert window.sidebar.brand.text() == "NCM OPS_"
    assert "monitoring / Dashboard" in window.topbar.breadcrumb.text()
```

- [ ] **Step 2: Create QSS theme**

Create `app_v4/desktop/theme/ops_terminal.qss`:

```css
QWidget { background: #0a0a0a; color: #fafaf7; font-family: "Geist"; }
QFrame#Sidebar { background: #111111; border-right: 1px solid #262626; }
QLabel#Brand { color: #ffb800; font-family: "JetBrains Mono"; letter-spacing: 2px; }
QPushButton { border: 1px solid #333333; border-radius: 0; padding: 8px; background: #141414; color: #fafaf7; }
QPushButton:hover { border-color: #ffb800; color: #ffb800; }
```

- [ ] **Step 3: Create sidebar/topbar**

Create `app_v4/desktop/shell/sidebar.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class Sidebar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        layout = QVBoxLayout(self)
        self.brand = QLabel("NCM OPS_")
        self.brand.setObjectName("Brand")
        layout.addWidget(self.brand)
        for label in ["Dashboard", "Switches", "Credentials", "History", "Diff", "Schedules", "Users", "Settings"]:
            layout.addWidget(QPushButton(label))
        layout.addStretch()
```

Create `app_v4/desktop/shell/topbar.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout


class Topbar(QFrame):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        self.breadcrumb = QLabel("monitoring / Dashboard")
        self.pulse = QLabel("service pulse · pending")
        layout.addWidget(self.breadcrumb)
        layout.addStretch()
        layout.addWidget(self.pulse)
```

- [ ] **Step 4: Create main window**

Create `app_v4/desktop/shell/main_window.py`:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QWidget, QVBoxLayout

from app_v4.desktop.shell.sidebar import Sidebar
from app_v4.desktop.shell.topbar import Topbar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NCM v4 Ops Terminal")
        self.resize(1280, 800)
        theme = Path(__file__).resolve().parents[1] / "theme" / "ops_terminal.qss"
        self.setStyleSheet(theme.read_text(encoding="utf-8"))

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = Sidebar()
        root_layout.addWidget(self.sidebar, 0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.topbar = Topbar()
        content_layout.addWidget(self.topbar)
        content_layout.addWidget(QLabel("Dashboard"), 1)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)
```

- [ ] **Step 5: Run shell test**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_shell.py -v
```

Expected: pass.

### Task 4: First-Run Setup Wizard Foundation

**Files:**
- Create: `app_v4/desktop/setup/wizard.py`
- Modify: `app_v4/desktop/main.py`
- Test: `app_v4/tests/test_desktop_setup_config.py`

- [ ] **Step 1: Create setup wizard**

Create `app_v4/desktop/setup/wizard.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWizard, QWizardPage, QVBoxLayout, QLabel


class SetupWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NCM v4 Setup")
        self.addPage(WelcomePage())
        self.addPage(ServicePage())
        self.addPage(AdminPage())


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Configure the NCM v4 service."))


class ServicePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Service")
        layout = QVBoxLayout(self)
        self.bind_host = QLineEdit("127.0.0.1")
        self.bind_port = QLineEdit("8443")
        layout.addWidget(QLabel("Bind host"))
        layout.addWidget(self.bind_host)
        layout.addWidget(QLabel("Bind port"))
        layout.addWidget(self.bind_port)


class AdminPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Admin")
        layout = QVBoxLayout(self)
        self.username = QLineEdit("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("Admin username"))
        layout.addWidget(self.username)
        layout.addWidget(QLabel("Admin password"))
        layout.addWidget(self.password)
```

- [ ] **Step 2: Create desktop entrypoint**

Create `app_v4/desktop/main.py`:

```python
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app_v4.desktop.shell.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run desktop test set**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_api_client.py app_v4/tests/test_desktop_setup_config.py app_v4/tests/test_desktop_shell.py -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```powershell
rtk git add app_v4/desktop app_v4/tests/test_desktop_setup_config.py app_v4/tests/test_desktop_shell.py
rtk git commit -m "feat: add v4 desktop shell and setup wizard"
```
