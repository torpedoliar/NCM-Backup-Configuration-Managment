from pathlib import Path

from app_v4.net.websmart_client import AsyncWebSmartClient

FX = Path(__file__).parent / "fixtures" / "network_doc"


def _client() -> AsyncWebSmartClient:
    return AsyncWebSmartClient.__new__(AsyncWebSmartClient)


def test_websmart_mib_dump_payload_is_accepted():
    text = (FX / "websmart.txt").read_text(encoding="utf-8")
    assert _client()._is_config_payload(text.encode(), text, "text/plain")


def test_websmart_v2_mib_dump_payload_is_accepted():
    text = (FX / "websmart_v2.txt").read_text(encoding="utf-8")
    assert _client()._is_config_payload(text.encode(), text, "text/plain")


def test_login_page_is_still_rejected():
    text = "<html><title>Login</title><form action='login.cgi'>user</form></html>"
    assert not _client()._is_config_payload(text.encode(), text, "text/html")
    assert not _client()._looks_like_config(text)


def test_dump_with_unused_vlan_named_invalid_is_accepted():
    text = (FX / "websmart.txt").read_text(encoding="utf-8") + "\n2\t.4.57\t 4\t   7\tinvalid"
    assert _client()._is_config_payload(text.encode(), text, "text/plain")
