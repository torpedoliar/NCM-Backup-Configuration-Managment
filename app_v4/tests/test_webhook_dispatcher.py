import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from app_v4.core.paths import resolve_paths
from app_v4.core.runtime_settings import NotifySettings, RuntimeSettings, load_runtime_settings, save_runtime_settings
from app_v4.service.app import create_app
from app_v4.service.events import EventHub, EventMessage
from app_v4.service.notify import Notifier
from app_v4.service.runtime import ServiceRuntime

SECRET = "whsec-test-123"


class _Hook(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        _Hook.received.append({"body": body, "sig": self.headers.get("X-NCM-Signature")})
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def hook_server():
    server = HTTPServer(("127.0.0.1", 0), _Hook)
    _Hook.received = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/hook"
    server.shutdown()


def _settings_path(test_settings):
    return resolve_paths(test_settings).data_dir / "runtime_settings.json"


def _write_notify(test_settings, **notify):
    path = _settings_path(test_settings)
    save_runtime_settings(path, RuntimeSettings(notify=NotifySettings(**notify)))
    return path


class RecordingNotifier:
    def __init__(self):
        self.calls = []

    async def webhook(self, payload):
        self.calls.append(payload)


@pytest.mark.asyncio
async def test_webhook_posts_hmac_signed_body(test_settings, hook_server):
    _write_notify(test_settings, enabled=True, webhook_url=hook_server, webhook_secret=SECRET)
    notifier = Notifier(_settings_path(test_settings))
    result = await notifier.webhook({"type": "backup_ok", "payload": {"switch_id": 1}, "ts": "t"})
    assert result.ok, result.detail
    assert len(_Hook.received) == 1
    body, sig = _Hook.received[0]["body"], _Hook.received[0]["sig"]
    expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert sig == f"sha256={expected}"
    assert json.loads(body)["type"] == "backup_ok"


@pytest.mark.asyncio
async def test_webhook_noop_without_secret_or_url(test_settings, hook_server):
    # disabled
    _write_notify(test_settings, enabled=False, webhook_url=hook_server, webhook_secret=SECRET)
    assert not (await Notifier(_settings_path(test_settings)).webhook({"a": 1})).ok
    # url kosong
    _write_notify(test_settings, enabled=True, webhook_url="", webhook_secret=SECRET)
    assert not (await Notifier(_settings_path(test_settings)).webhook({"a": 1})).ok
    # secret kosong
    _write_notify(test_settings, enabled=True, webhook_url=hook_server, webhook_secret="")
    assert not (await Notifier(_settings_path(test_settings)).webhook({"a": 1})).ok
    assert _Hook.received == []


@pytest.mark.asyncio
async def test_dispatcher_maps_and_filters_events():
    notifier = RecordingNotifier()
    hub = EventHub(notifier=notifier)
    await hub.broadcast(EventMessage.create("backup_completed", {"switch_id": 1}))
    await hub.broadcast(EventMessage.create("backup_started", {"switch_id": 1}))  # bukan event tiket
    await hub.broadcast(EventMessage.create("config_drift", {"review_id": 7}))
    assert [(c["type"], c["payload"]) for c in notifier.calls] == [
        ("backup_ok", {"switch_id": 1}),
        ("drift", {"review_id": 7}),
        ("review_opened", {"review_id": 7}),
    ]


@pytest.mark.asyncio
async def test_dispatcher_silent_without_notifier():
    hub = EventHub()  # tanpa notifier: broadcast jalan seperti biasa, tanpa error
    await hub.broadcast(EventMessage.create("backup_failed", {"x": 1}))


@pytest.mark.asyncio
async def test_webhook_secret_settable_via_system_api_and_e2e_signed(test_settings, session_factory, hook_server):
    from app_v4.data.repository import Repository

    async with session_factory() as session:
        await Repository(session).create_user("admin", "h", "admin")
        await session.commit()
    runtime = ServiceRuntime.for_tests(
        test_settings, session_factory, jwt_secret=b"w" * 32,
        event_hub=EventHub(notifier=Notifier(_settings_path(test_settings))),
    )
    client = TestClient(create_app(runtime))
    hdr = {"Authorization": f"Bearer {runtime.auth_service.issue_access_token(1, 'admin', 'admin')}"}

    r = client.patch("/api/v1/system/notify-settings", headers=hdr,
                     json={"enabled": True, "webhook_url": hook_server, "webhook_secret": SECRET})
    assert r.status_code == 200, r.text
    assert r.json()["webhook_secret"] == SECRET
    assert load_runtime_settings(_settings_path(test_settings)).notify.webhook_secret == SECRET

    await runtime.event_hub.broadcast(EventMessage.create("backup_completed", {"switch_id": 3}))
    assert len(_Hook.received) == 1
    body = _Hook.received[0]["body"]
    expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert _Hook.received[0]["sig"] == f"sha256={expected}"
    assert json.loads(body) == {"type": "backup_ok", "payload": {"switch_id": 3}, "ts": json.loads(body)["ts"]}
