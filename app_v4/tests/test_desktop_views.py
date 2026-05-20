import pytest

from app_v4.desktop.views.dashboard_view import DashboardView
from app_v4.desktop.views.history_view import HistoryView
from app_v4.desktop.views.diff_view import DiffView
from app_v4.desktop.views.inventory_view import InventoryView
from app_v4.desktop.views.credentials_view import CredentialsView
from app_v4.desktop.views.schedules_view import SchedulesView
from app_v4.desktop.views.users_view import UsersView
from app_v4.desktop.views.settings_view import SettingsView


@pytest.mark.parametrize("cls,path", [(DashboardView, "/"), (HistoryView, "/history"), (DiffView, "/diff")])
def test_webengine_view_targets_service_route(qtbot, cls, path):
    view = cls("http://127.0.0.1:8443")
    qtbot.addWidget(view)
    assert view.target_url.endswith(path)


@pytest.mark.parametrize("cls,title", [(InventoryView, "Inventory"), (CredentialsView, "Credentials"), (SchedulesView, "Schedules"), (UsersView, "Users"), (SettingsView, "Settings")])
def test_native_views_render_titles(qtbot, cls, title):
    view = cls()
    qtbot.addWidget(view)
    assert view.title.text() == title
