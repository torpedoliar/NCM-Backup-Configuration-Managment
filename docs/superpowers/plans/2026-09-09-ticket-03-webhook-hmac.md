# Plan: Tiket 03 — NCM event webhook + HMAC dispatcher

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enam event NCM (`backup_failed`, `backup_ok`, `drift`, `review_opened`, `review_decided`, `device_offline`) terkirim sebagai JSON ke `webhook_url`, ditandatangani HMAC-SHA256 (`X-NCM-Signature: sha256=<hex>`) dengan `webhook_secret`. Tanpa secret/URL/enabled = no-op aman (tidak ada attempt, tidak ada error log).

**Architecture:** Satu titik panggil: `EventHub.broadcast` adalah choke point yang sudah dilalui SEMUA `publish()` (backup_service, scheduler, jobs) — pasang webhook fanout di situ via `Notifier` yang di-inject ke konstruktor (tanpa import melingkar). Mapping nama event internal → eksternal di satu tabel `WEBHOOK_EVENT_MAP` di `events.py`: `backup_completed`→`backup_ok`, `config_drift`→(`drift` + `review_opened`), sisanya identitas. Event yang belum pernah di-publish: `device_offline` (dari backup gagal ber-`error_code == CONNECTION_TIMEOUT` di `backup_service`), `review_opened` (dari `refresh_baseline` bila review dibuka), `review_decided` (dari `update_review_status` + `promote_review_to_baseline` di `reviews.py`). `Notifier.webhook()` (dead-code) dihidupkan: guard 3 kondisi (enabled/url/secret), serialize JSON sekali, HMAC-SHA256 stdlib `hmac/hashlib` atas body persis yang dikirim, header via `_post_json` yang menerima `bytes` + headers. `webhook_secret: str = ""` field baru di `NotifySettings` (load/save otomatis via filter `__dataclass_fields__`), diset via `PATCH /system/notify-settings` (pola sama dengan field notify lain; response mengikuti preseden `smtp_password` yang sudah terekspos). Payload webhook = bentuk `EventMessage` (`{type, payload, ts}`) dengan `type` = nama eksternal.

**Tech Stack:** Python 3, FastAPI, stdlib `hmac/hashlib/http.server` (test), pytest + TestClient. No new dependencies.

**Spec:** `.scratch/ncm-manage/SPEC.md`. **Ticket:** `.scratch/ncm-manage/issues/03-ncm-webhook-hmac.md`. **Depends on:** tiket 01 (commit 4beb5ef).

## Global Constraints

- No new third-party dependencies — stdlib only (`hmac`, `hashlib`, `http.server` di test).
- Webhook TIDAK PERNAH boleh mematahkan jalur backup/review/broadcast: kegagalan kirim → log + NotifyResult, tanpa raise (pola best-effort `Notifier` existing).
- Tanpa `enabled` ATAU `webhook_url` ATAU `webhook_secret` → tidak ada attempt kirim sama sekali, tidak ada warning/error di log.
- Signature dihitung atas byte body persis yang dikirim (`json.dumps` sekali, encode utf-8, hex digest HMAC-SHA256).
- Event websocket existing (backup_started, job_triggered, connected, dst.) TIDAK terkirim ke webhook — hanya 6 event tiket.
- API errors pakai `problem(status, title, detail)`; PATCH notify-settings mengikuti pola field notify lain (exclude_none).
- Test acuan: `app_v4/tests/test_events_integration.py` (RecordingHub) + `test_system_api.py` (for_tests/TestClient); suite 430 baseline harus tetap hijau.
- ponytail: satu tabel mapping event, satu fanout di `broadcast`, tanpa antrean/retry, tanpa class dispatcher baru — `EventHub` + `Notifier.webhook` cukup. (Retry/t antrean = upgrade path bila DG ingest drop event.)

## File Structure

Modified:
- `app_v4/core/runtime_settings.py` — `NotifySettings.webhook_secret: str = ""` (satu baris).
- `app_v4/service/events.py` — `WEBHOOK_EVENT_MAP`, `EventHub(notifier=None)`, fanout `_webhook` di `broadcast`.
- `app_v4/service/notify.py` — `webhook()` hidup + HMAC; `_post_json(url, body: bytes, headers=None)`; telegram call-site sesuaikan.
- `app_v4/service/runtime.py` — build_runtime: buat `notify` sebelum `event_hub`, inject; `for_tests` terima `event_hub=None` opsional.
- `app_v4/service/api/system.py` — `NotifySettingsPatch.webhook_secret`, wiring di `patch_notify_settings`, field di response.
- `app_v4/service/api/reviews.py` — publish `review_opened` (refresh_baseline), `review_decided` (update_review_status + promote).
- `app_v4/service/backup_service.py` — publish `device_offline` bila `error_code == "CONNECTION_TIMEOUT"` (2 titik gagal).
- `.scratch/ncm-manage/issues/03-ncm-webhook-hmac.md` — tandai done saat hijau.

New:
- `app_v4/tests/test_webhook_dispatcher.py` — HMAC signature + no-op + mapping + PATCH secret + e2e event→signed POST.

Out of scope: retry/antrean pengiriman, webhook per-event-type toggle, publish review_opened dari fleet run-cycle (dibuka bila DG butuh), sisi ingest DG (tiket 06).

---

### Task 1: Secret field + Notifier.webhook HMAC + dispatcher EventHub + titik publish

**Files:** semua Modified di atas + test baru.

**Interfaces:**
- Consumes: `Notifier._post_json`, `EventHub.broadcast`, `publish()`, `NotifySettings`, pola `runtime_settings_lock` di system.py.
- Produces:
  - `NotifySettings.webhook_secret: str = ""`.
  - `Notifier.webhook(payload) -> NotifyResult` — no-op (`ok=False`, detail jelas) bila `not enabled or not webhook_url or not webhook_secret`; else POST JSON dengan header `X-NCM-Signature: sha256=<hmac_sha256_hex(secret, body)>`.
  - `EventHub(notifier=None)`; `broadcast` memanggil `notifier.webhook({"type": mapped, "payload": ..., "ts": ...})` untuk tiap nama di `WEBHOOK_EVENT_MAP.get(event.type, ())`, try/except total.
  - `ServiceRuntime.for_tests(..., event_hub: EventHub | None = None)`.
  - `PATCH /api/v1/system/notify-settings` menerima/menyimpan/mengembalikan `webhook_secret`.
  - Event baru: `device_offline` {switch_id, switch_name, backup_id}; `review_opened` {switch_id, switch_name, backup_id, review_id}; `review_decided` {review_id, switch_id, status, comment}.

- [ ] **Step 1: Write the failing test**

Buat `app_v4/tests/test_webhook_dispatcher.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:/+SYNO+/Home/1. Project Windsurf/Test Project" && ./.venv/Scripts/python.exe -m pytest app_v4/tests/test_webhook_dispatcher.py -q -p no:warnings`
Expected: FAIL — `NotifySettings` tak kenal `webhook_secret` (TypeError), `EventHub` tak terima `notifier`, PATCH `webhook_secret` diabaikan/ditolak.

- [ ] **Step 3: Write minimal implementation**

1. `runtime_settings.py`: field `webhook_secret: str = ""` di `NotifySettings` (load/save otomatis).
2. `notify.py`: import `hmac`, `hashlib`. `webhook()`: guard `enabled/webhook_url/webhook_secret` → no-op result; `body = json.dumps(payload, separators=(",", ":")).encode("utf-8")`; `sig = hmac.new(cfg.webhook_secret.encode(), body, hashlib.sha256).hexdigest()`; `return self._post_json(cfg.webhook_url, body, {"X-NCM-Signature": f"sha256={sig}"})`. `_post_json(self, url, body: bytes, headers: dict | None = None)` — merge headers ke dict Content-Type; call-site telegram: `self._post_json(url, json.dumps(payload).encode("utf-8"))`.
3. `events.py`: `WEBHOOK_EVENT_MAP = {"backup_failed": ("backup_failed",), "backup_completed": ("backup_ok",), "config_drift": ("drift", "review_opened"), "review_opened": ("review_opened",), "review_decided": ("review_decided",), "device_offline": ("device_offline",)}`; `EventHub.__init__(self, notifier=None)`; di akhir `broadcast`: `await self._webhook(event)`; `_webhook`: skip tanpa notifier; loop mapped names, `try: await self._notifier.webhook({"type": name, "payload": event.payload, "ts": event.ts}) except Exception: logger.warning(...)` (tambah `logger = logging.getLogger(__name__)`).
4. `runtime.py`: `build_runtime` — pindahkan `notify = Notifier(...)` ke atas `event_hub = EventHub(notifier=notify)`; `for_tests` — param `event_hub: EventHub | None = None`, pakai `event_hub or EventHub()`.
5. `system.py`: `NotifySettingsPatch.webhook_secret: str | None = Field(default=None, max_length=500)`; `NotifySettingsResponse.webhook_secret: str`; `_build_notify_response` + `patch_notify_settings` wiring (`webhook_secret=updates.get("webhook_secret", old.webhook_secret)`).
6. `backup_service.py` — setelah dua publish `backup_failed` (exception path + `run_result.success == False` path): `if result.get("error_code") == "CONNECTION_TIMEOUT": await publish(self.event_hub, "device_offline", {"switch_id": ..., "switch_name": ..., "backup_id": result["backup_id"]})` (exception path pakai `switch.name`).
7. `reviews.py`: import `publish`; `refresh_baseline` — bila `review_id` tidak None: `await publish(runtime.event_hub, "review_opened", {"switch_id": review_switch.id, "switch_name": review_switch.name, "backup_id": target.id, "review_id": review_id})`; `update_review_status` — `await publish(runtime.event_hub, "review_decided", {"review_id": review_id, "switch_id": review.switch_id, "status": payload.status, "comment": payload.comment})`; `promote_review_to_baseline` — sama dengan status `"approved"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:/+SYNO+/Home/1. Project Windsurf/Test Project" && ./.venv/Scripts/python.exe -m pytest app_v4/tests/test_webhook_dispatcher.py app_v4/tests/test_events_integration.py app_v4/tests/test_system_api.py app_v4/tests/test_websocket.py app_v4/tests/test_backup_service.py -q -p no:warnings`
Expected: PASS semua.

- [ ] **Step 5: Run full suite + commit**

Run: `./.venv/Scripts/python.exe -m pytest app_v4/tests/ -q -p no:warnings` (430 baseline + 5 baru = 435 hijau).
Run: `git add -A && git commit -m "feat: event webhook + HMAC-SHA256 dispatcher (ticket 03)"`
Tandai tiket 03 done di `.scratch/ncm-manage/issues/03-ncm-webhook-hmac.md`.
Do NOT push without explicit consent.
