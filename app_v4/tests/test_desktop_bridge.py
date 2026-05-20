from app_v4.desktop.bridge.web_bridge import WebBridge


def test_web_bridge_exposes_service_context(qtbot):
    bridge = WebBridge("http://127.0.0.1:8443", "token")
    assert bridge.serviceUrl() == "http://127.0.0.1:8443"
    assert bridge.accessToken() == "token"
