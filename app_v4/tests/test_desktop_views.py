import pytest

from app_v4.desktop.shell.spa_view import SpaView
from app_v4.desktop.views.dashboard_view import DashboardView
from app_v4.desktop.views.diff_view import DiffView
from app_v4.desktop.views.history_view import HistoryView


@pytest.mark.parametrize(
    "cls,path",
    [
        (DashboardView, "/"),
        (HistoryView, "/history"),
        (DiffView, "/diff"),
    ],
)
def test_legacy_webengine_view_targets_service_route(qtbot, cls, path):
    view = cls("http://127.0.0.1:8443")
    qtbot.addWidget(view)
    assert view.target_url.endswith(path)


def test_spa_view_loads_root_and_navigates(qtbot):
    view = SpaView(
        service_url="http://127.0.0.1:8443/",
        access_token="token-abc",
        refresh_token="refresh-def",
    )
    qtbot.addWidget(view)

    assert view.service_url == "http://127.0.0.1:8443"
    # navigate() builds a JS pushState — assert it doesn't raise on a non-leading-slash input
    view.navigate("switches")
    view.navigate("/credentials")


def test_spa_view_token_injection_script_is_registered(qtbot):
    view = SpaView(
        service_url="http://127.0.0.1:8443",
        access_token='quote"and\\backslash',
        refresh_token="refresh",
    )
    qtbot.addWidget(view)

    # The injection script should be registered on the page so it runs at
    # DocumentCreation, before the SPA's React mount reads localStorage.
    scripts = view.page().scripts()
    matches = [s for s in scripts.find("ncm-v4-token-injector")]
    assert matches, "expected token injection script to be registered"
    source = matches[0].sourceCode()
    assert 'localStorage.setItem("access_token"' in source
    assert 'localStorage.setItem("refresh_token"' in source
    # Quotes and backslashes in tokens must be escaped, not break the JS string literal
    assert '\\"' in source
    assert '\\\\' in source
