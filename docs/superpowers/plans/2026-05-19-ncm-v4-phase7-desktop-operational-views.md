# NCM v4 Phase 7 Desktop Operational Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the desktop shell with operational views and connect visual-heavy pages to the React web bundle through QWebEngineView.

**Architecture:** Keep forms native Qt for inventory, credentials, schedules, users, and settings. Use QWebEngineView for dashboard, history, and diff routes so charts/diff visuals are shared with the web client. Add a small QWebChannel bridge for native-to-web service context.

**Tech Stack:** PySide6, PySide6.QtWebEngineWidgets, PySide6.QtWebChannel, httpx, pytest, pytest-qt.

---

## File Structure

- Modify: `app_v4/desktop/shell/main_window.py` — route sidebar buttons to view stack.
- Modify: `app_v4/desktop/shell/sidebar.py` — expose named signals/buttons.
- Create: `app_v4/desktop/views/dashboard_view.py`
- Create: `app_v4/desktop/views/inventory_view.py`
- Create: `app_v4/desktop/views/credentials_view.py`
- Create: `app_v4/desktop/views/history_view.py`
- Create: `app_v4/desktop/views/diff_view.py`
- Create: `app_v4/desktop/views/schedules_view.py`
- Create: `app_v4/desktop/views/users_view.py`
- Create: `app_v4/desktop/views/settings_view.py`
- Create: `app_v4/desktop/bridge/web_bridge.py`
- Create: `app_v4/desktop/theme/generate_qss.py`
- Test: `app_v4/tests/test_desktop_views.py`
- Test: `app_v4/tests/test_desktop_bridge.py`
- Test: `app_v4/tests/test_desktop_theme_generator.py`

### Task 1: WebEngine Views for Visual Pages

**Files:**
- Create: `app_v4/desktop/views/dashboard_view.py`
- Create: `app_v4/desktop/views/history_view.py`
- Create: `app_v4/desktop/views/diff_view.py`
- Test: `app_v4/tests/test_desktop_views.py`

- [ ] **Step 1: Write view tests**

Create `app_v4/tests/test_desktop_views.py`:

```python
import pytest

from app_v4.desktop.views.dashboard_view import DashboardView
from app_v4.desktop.views.history_view import HistoryView
from app_v4.desktop.views.diff_view import DiffView


@pytest.mark.qt
@pytest.mark.parametrize("cls,path", [(DashboardView, "/"), (HistoryView, "/history"), (DiffView, "/diff")])
def test_webengine_view_targets_service_route(qtbot, cls, path):
    view = cls("http://127.0.0.1:8443")
    qtbot.addWidget(view)
    assert view.target_url.endswith(path)
```

- [ ] **Step 2: Create WebEngine view classes**

Create `app_v4/desktop/views/dashboard_view.py`:

```python
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView


class DashboardView(QWebEngineView):
    def __init__(self, service_url: str):
        super().__init__()
        self.target_url = service_url.rstrip("/") + "/"
        self.setUrl(QUrl(self.target_url))
```

Create `history_view.py` and `diff_view.py` with the same pattern and `"/history"` / `"/diff"` paths.

- [ ] **Step 3: Run view tests**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_views.py -v
```

Expected: pass.

### Task 2: Native Form Views

**Files:**
- Create: `app_v4/desktop/views/inventory_view.py`
- Create: `app_v4/desktop/views/credentials_view.py`
- Create: `app_v4/desktop/views/schedules_view.py`
- Create: `app_v4/desktop/views/users_view.py`
- Create: `app_v4/desktop/views/settings_view.py`
- Test: `app_v4/tests/test_desktop_views.py`

- [ ] **Step 1: Add native view test**

Append to `test_desktop_views.py`:

```python
from app_v4.desktop.views.inventory_view import InventoryView
from app_v4.desktop.views.credentials_view import CredentialsView
from app_v4.desktop.views.schedules_view import SchedulesView
from app_v4.desktop.views.users_view import UsersView
from app_v4.desktop.views.settings_view import SettingsView


@pytest.mark.qt
@pytest.mark.parametrize("cls,title", [(InventoryView, "Inventory"), (CredentialsView, "Credentials"), (SchedulesView, "Schedules"), (UsersView, "Users"), (SettingsView, "Settings")])
def test_native_views_render_titles(qtbot, cls, title):
    view = cls()
    qtbot.addWidget(view)
    assert view.title.text() == title
```

- [ ] **Step 2: Create native view base pattern**

Create `app_v4/desktop/views/inventory_view.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTableView, QVBoxLayout, QWidget


class InventoryView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.title = QLabel("Inventory")
        layout.addWidget(self.title)
        layout.addWidget(QPushButton("Add switch"))
        layout.addWidget(QTableView())
```

Create the other four files with titles/actions:
- `CredentialsView`: title `Credentials`, button `Add credential`.
- `SchedulesView`: title `Schedules`, button `Add schedule`.
- `UsersView`: title `Users`, button `Add user`.
- `SettingsView`: title `Settings`, labels `Service`, `Branding`, `Retention`, `Logs`, `About`.

- [ ] **Step 3: Run native view tests**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_views.py -v
```

Expected: pass.

### Task 3: Main Window View Stack Navigation

**Files:**
- Modify: `app_v4/desktop/shell/sidebar.py`
- Modify: `app_v4/desktop/shell/main_window.py`
- Test: `app_v4/tests/test_desktop_shell.py`

- [ ] **Step 1: Add navigation test**

Append to `app_v4/tests/test_desktop_shell.py`:

```python
def test_main_window_switches_to_inventory(qtbot):
    window = MainWindow(service_url="http://127.0.0.1:8443")
    qtbot.addWidget(window)
    window.sidebar.buttons["Switches"].click()
    assert window.stack.currentWidget().__class__.__name__ == "InventoryView"
```

- [ ] **Step 2: Expose sidebar buttons**

In `Sidebar`, store:

```python
self.buttons: dict[str, QPushButton] = {}
...
button = QPushButton(label)
self.buttons[label] = button
layout.addWidget(button)
```

- [ ] **Step 3: Add QStackedWidget to main window**

In `MainWindow.__init__`, accept `service_url: str = "http://127.0.0.1:8443"`, create:

```python
self.stack = QStackedWidget()
self.views = {
    "Dashboard": DashboardView(service_url),
    "Switches": InventoryView(),
    "Credentials": CredentialsView(),
    "History": HistoryView(service_url),
    "Diff": DiffView(service_url),
    "Schedules": SchedulesView(),
    "Users": UsersView(),
    "Settings": SettingsView(),
}
for name, view in self.views.items():
    self.stack.addWidget(view)
    self.sidebar.buttons[name].clicked.connect(lambda checked=False, n=name: self.stack.setCurrentWidget(self.views[n]))
```

- [ ] **Step 4: Run shell tests**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_shell.py app_v4/tests/test_desktop_views.py -v
```

Expected: pass.

### Task 4: QWebChannel Bridge

**Files:**
- Create: `app_v4/desktop/bridge/web_bridge.py`
- Test: `app_v4/tests/test_desktop_bridge.py`

- [ ] **Step 1: Write bridge test**

Create `app_v4/tests/test_desktop_bridge.py`:

```python
from app_v4.desktop.bridge.web_bridge import WebBridge


def test_web_bridge_exposes_service_context():
    bridge = WebBridge("http://127.0.0.1:8443", "token")
    assert bridge.serviceUrl() == "http://127.0.0.1:8443"
    assert bridge.accessToken() == "token"
```

- [ ] **Step 2: Create bridge**

Create `app_v4/desktop/bridge/web_bridge.py`:

```python
from __future__ import annotations

from PySide6.QtCore import QObject, Slot


class WebBridge(QObject):
    def __init__(self, service_url: str, access_token: str | None = None):
        super().__init__()
        self._service_url = service_url
        self._access_token = access_token or ""

    @Slot(result=str)
    def serviceUrl(self) -> str:
        return self._service_url

    @Slot(result=str)
    def accessToken(self) -> str:
        return self._access_token
```

- [ ] **Step 3: Run bridge test**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_bridge.py -v
```

Expected: pass.

### Task 5: QSS Token Generator

**Files:**
- Create: `app_v4/desktop/theme/generate_qss.py`
- Test: `app_v4/tests/test_desktop_theme_generator.py`

- [ ] **Step 1: Write generator test**

Create `app_v4/tests/test_desktop_theme_generator.py`:

```python
from pathlib import Path

from app_v4.desktop.theme.generate_qss import generate_qss


def test_generate_qss_maps_tokens(tmp_path):
    tokens = tmp_path / "tokens.css"
    tokens.write_text(":root { --ink: #0a0a0a; --amber: #ffb800; --bone: #fafaf7; }", encoding="utf-8")

    qss = generate_qss(tokens)

    assert "#0a0a0a" in qss
    assert "#ffb800" in qss
    assert "#fafaf7" in qss
```

- [ ] **Step 2: Create generator**

Create `app_v4/desktop/theme/generate_qss.py`:

```python
from __future__ import annotations

import re
from pathlib import Path


def generate_qss(tokens_path: Path) -> str:
    text = tokens_path.read_text(encoding="utf-8")
    tokens = dict(re.findall(r"--([a-z0-9-]+):\s*([^;]+);", text))
    return f"""
QWidget {{ background: {tokens['ink'].strip()}; color: {tokens['bone'].strip()}; }}
QLabel#Brand {{ color: {tokens['amber'].strip()}; }}
QPushButton:hover {{ border-color: {tokens['amber'].strip()}; }}
""".strip()
```

- [ ] **Step 3: Run all desktop tests**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_api_client.py app_v4/tests/test_desktop_setup_config.py app_v4/tests/test_desktop_shell.py app_v4/tests/test_desktop_views.py app_v4/tests/test_desktop_bridge.py app_v4/tests/test_desktop_theme_generator.py -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```powershell
rtk git add app_v4/desktop app_v4/tests/test_desktop_views.py app_v4/tests/test_desktop_bridge.py app_v4/tests/test_desktop_theme_generator.py app_v4/tests/test_desktop_shell.py
rtk git commit -m "feat: add v4 desktop operational views"
```
