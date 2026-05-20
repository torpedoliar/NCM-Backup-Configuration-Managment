# NCM v4 Backend Execution Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add async-native WebSmart HTTP/HTTPS backup support to the v4 backup runner created in Phase 1.

**Architecture:** Execute this only after Phase 1 passes. Keep `app/` untouched and add a v4-native async WebSmart client under `app_v4/net/`. The existing Phase 1 `BackupService` and backups API keep their shape; Phase 2 expands `BackupRunner` protocol support so switches using `http`, `https`, `websmart`, and `websmart-v2` can run through the same backup flow.

**Tech Stack:** FastAPI, async SQLAlchemy 2, aiohttp, BeautifulSoup4, cryptography RSA PKCS#1 v1.5 encryption, pytest-asyncio, aiohttp local test server. All terminal commands must use `rtk`.

---

## File Structure

Create:

```text
app_v4/net/websmart_client.py
app_v4/tests/test_websmart_client.py
```

Modify:

```text
app_v4/requirements-v4.txt
app_v4/net/runner.py
app_v4/tests/test_backup_runner.py
```

Do not modify `app/`.

---

## Task 1: Add Phase 2 WebSmart dependencies

**Files:**
- Modify: `app_v4/requirements-v4.txt`

- [ ] **Step 1: Update requirements**

Append these lines to `app_v4/requirements-v4.txt` if missing:

```text
aiohttp>=3.10.0
beautifulsoup4>=4.12.0
```

Do not add `pycryptodome`; the v4 client uses the existing `cryptography` dependency for WebSmart V2 RSA encryption.

- [ ] **Step 2: Install requirements**

```bash
rtk python -m pip install -r app_v4/requirements-v4.txt
```

Expected: install succeeds.

- [ ] **Step 3: Verify imports**

```bash
rtk python -c "import aiohttp, bs4; print('ok')"
```

Expected:

```text
ok
```

- [ ] **Step 4: Commit**

```bash
rtk git add app_v4/requirements-v4.txt
rtk git commit -m "chore: add v4 WebSmart dependencies"
```

---

## Task 2: Add async WebSmart client tests

**Files:**
- Create: `app_v4/tests/test_websmart_client.py`

- [ ] **Step 1: Write failing tests**

Create `app_v4/tests/test_websmart_client.py`:

```python
from __future__ import annotations

from aiohttp import web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

from app_v4.net.websmart_client import AsyncWebSmartClient


async def _start_server(app: web.Application) -> tuple[web.AppRunner, int]:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    sockets = site._server.sockets
    assert sockets is not None
    return runner, sockets[0].getsockname()[1]


@pytest.mark.asyncio
async def test_traditional_websmart_login_downloads_direct_config():
    seen_login = []

    async def login(request: web.Request) -> web.Response:
        data = await request.post()
        seen_login.append((data["Login"], data["Password"]))
        return web.Response(
            text='<html><input name="Gambit" value="abc123"></html>',
            content_type="text/html",
        )

    async def config(request: web.Request) -> web.Response:
        assert request.query["Gambit"] == "abc123"
        return web.Response(text="hostname sw01\ninterface 1", content_type="text/plain")

    app = web.Application()
    app.router.add_post("/iss/redirect.html", login)
    app.router.add_get("/iss1.conf", config)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient("127.0.0.1", port, "admin", "secret", timeout=5)
    try:
        assert await client.connect() is True
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert seen_login == [("admin", "secret")]
    assert text == "hostname sw01\ninterface 1"


@pytest.mark.asyncio
async def test_traditional_websmart_submits_backup_form():
    submitted = []

    async def login(request: web.Request) -> web.Response:
        await request.post()
        return web.Response(text="<html>logged in</html>", content_type="text/html")

    async def backup_page(request: web.Request) -> web.Response:
        return web.Response(
            text="""
            <html>
              <form action="/download" method="post">
                <input type="hidden" name="session" value="s1">
                <input type="submit" name="b_save" value="Backup">
              </form>
            </html>
            """,
            content_type="text/html",
        )

    async def download(request: web.Request) -> web.Response:
        data = await request.post()
        submitted.append(dict(data))
        return web.Response(text="sysname sw-form\nconfig line", content_type="text/plain")

    app = web.Application()
    app.router.add_post("/iss/redirect.html", login)
    app.router.add_get("/iss/config_file_http.html", backup_page)
    app.router.add_post("/download", download)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient("127.0.0.1", port, "admin", "secret", timeout=5)
    try:
        assert await client.connect() is True
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert submitted == [{"b_save": "Backup", "session": "s1"}]
    assert text == "sysname sw-form\nconfig line"


@pytest.mark.asyncio
async def test_websmart_v2_login_uses_rsa_token_flow():
    seen_params = []
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    escaped_public_pem = public_pem.replace("\n", "\\n")

    async def public_key(request: web.Request) -> web.Response:
        return web.Response(
            text=f'window.web_pub_key = "{escaped_public_pem}";',
            content_type="application/javascript",
        )

    async def login(request: web.Request) -> web.Response:
        seen_params.append(dict(request.query))
        return web.json_response({"gambit": "v2token"})

    async def config(request: web.Request) -> web.Response:
        assert request.query["Gambit"] == "v2token"
        return web.Response(text="hostname v2\ninterface 2", content_type="text/plain")

    app = web.Application()
    app.router.add_get("/iss/specific/web_pub_key_data.js", public_key)
    app.router.add_get("/iss/specific/web_login_data.js", login)
    app.router.add_get("/iss1.conf", config)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient(
        "127.0.0.1",
        port,
        "manager",
        "friend",
        timeout=5,
        force_v2_only=True,
    )
    try:
        assert await client.connect() is True
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert seen_params
    assert seen_params[0]["pelican"]
    assert seen_params[0]["pinkpanther"]
    assert text == "hostname v2\ninterface 2"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_websmart_client.py -v
```

Expected: FAIL with missing `app_v4.net.websmart_client`.

- [ ] **Step 3: Commit failing tests**

```bash
rtk git add app_v4/tests/test_websmart_client.py
rtk git commit -m "test: cover v4 WebSmart client flows"
```

---

## Task 3: Add async WebSmart client

**Files:**
- Create: `app_v4/net/websmart_client.py`
- Test: `app_v4/tests/test_websmart_client.py`

- [ ] **Step 1: Create WebSmart client**

Create `app_v4/net/websmart_client.py`:

```python
from __future__ import annotations

import base64
import json
import re
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


class AsyncWebSmartClient:
    def __init__(
        self,
        host: str,
        port: int = 80,
        username: str = "manager",
        password: str = "friend",
        timeout: int = 30,
        scheme: str = "http",
        force_v2_only: bool = False,
        session: aiohttp.ClientSession | None = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.scheme = scheme
        self.base_url = f"{scheme}://{host}:{port}/"
        self.force_v2_only = force_v2_only
        self.gambit_token: str | None = None
        self._owns_session = session is None
        self.session = session or aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

    async def connect(self) -> bool:
        if self.force_v2_only:
            if await self._try_v2_login():
                return True
            raise ConnectionError("V2 authentication failed. Check WebSmart V2 model and credentials.")
        return await self._try_traditional_login()

    async def enter_enable_mode(self, prompts: list[str]) -> bool:
        return True

    async def disable_paging(self, commands: list[str]) -> bool:
        return True

    async def get_running_config(self, paging_indicators: list[str] | None = None) -> str:
        endpoints: list[str] = []
        if self.gambit_token:
            endpoints.extend(
                [
                    f"iss1.conf?Gambit={self.gambit_token}",
                    f"iss.conf?Gambit={self.gambit_token}",
                ]
            )
        endpoints.extend(
            [
                "iss1.conf",
                "iss.conf",
                "iss/config_file_http.html",
                "config.bin",
                "backup.cgi",
                "config/backup.cgi",
                "system/config_backup.htm",
                "maintenance/upload_download.htm",
            ]
        )

        last_url = self.base_url
        for endpoint in endpoints:
            last_url = urljoin(self.base_url, endpoint)
            try:
                async with self.session.get(last_url, timeout=self._timeout()) as response:
                    text = await response.text()
                    if response.status != 200:
                        continue
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "text/html" not in content_type and text:
                        return text
                    if endpoint == "iss/config_file_http.html" and "text/html" in content_type:
                        form_result = await self._submit_backup_form(last_url, text)
                        if form_result:
                            return form_result
            except aiohttp.ClientError:
                continue

        raise ValueError(f"Could not find a valid configuration download endpoint from {last_url}")

    async def disconnect(self) -> None:
        try:
            await self.session.get(urljoin(self.base_url, "logout.cgi"), timeout=aiohttp.ClientTimeout(total=5))
        except Exception:
            pass
        if self._owns_session:
            await self.session.close()

    async def _try_traditional_login(self) -> bool:
        attempts = [
            ("iss/redirect.html", {"Login": self.username, "Password": self.password}),
            ("iss/login.cgi", {"username": self.username, "password": self.password, "submit": "Login"}),
            ("iss/login.html", {"username": self.username, "password": self.password, "submit": "Login"}),
            ("login.cgi", {"username": self.username, "password": self.password, "submit": "Login"}),
            ("logon.htm", {"user": self.username, "password": self.password}),
        ]
        for path, data in attempts:
            target_url = urljoin(self.base_url, path)
            try:
                async with self.session.post(
                    target_url,
                    data=data,
                    timeout=self._timeout(),
                    allow_redirects=True,
                ) as response:
                    text = await response.text()
                    if response.status != 200:
                        continue
                    self._extract_gambit(text)
                    response_url = str(response.url).lower()
                    if "login" not in response_url and "logon" not in response_url:
                        return True
                    if "iss/" in response_url:
                        return True
                    if not self._has_failure_text(text):
                        return True
            except aiohttp.ClientError:
                continue
        raise ConnectionError("Failed to login to WebSmart switch. Check credentials or network.")

    async def _try_v2_login(self) -> bool:
        try:
            pubkey_url = urljoin(self.base_url, "iss/specific/web_pub_key_data.js")
            async with self.session.get(pubkey_url, timeout=self._timeout()) as response:
                if response.status != 200:
                    return False
                pubkey_text = await response.text()
            pubkey_pem = self._extract_public_key(pubkey_text)
            if pubkey_pem is None:
                return False

            public_key = serialization.load_pem_public_key(pubkey_pem.encode("utf-8"))
            pelican = base64.b64encode(
                public_key.encrypt(self.username.encode("utf-8"), padding.PKCS1v15())
            ).decode("utf-8")
            pinkpanther = base64.b64encode(
                public_key.encrypt(self.password.encode("utf-8"), padding.PKCS1v15())
            ).decode("utf-8")

            login_url = urljoin(self.base_url, "iss/specific/web_login_data.js")
            async with self.session.get(
                login_url,
                params={"pelican": pelican, "pinkpanther": pinkpanther},
                timeout=self._timeout(),
            ) as response:
                if response.status != 200:
                    return False
                body = await response.text()
            data = json.loads(body)
            gambit = data.get("gambit")
            if not isinstance(gambit, str) or not gambit:
                return False
            self.gambit_token = gambit
            return True
        except (aiohttp.ClientError, ValueError, TypeError, json.JSONDecodeError):
            return False

    async def _submit_backup_form(self, page_url: str, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        for form in soup.find_all("form"):
            backup_button = self._find_backup_button(form)
            if backup_button is None:
                continue
            action = form.get("action", "")
            post_url = urljoin(page_url, action) if action else page_url
            data: dict[str, str] = {}
            button_name = backup_button.get("name")
            if button_name:
                data[button_name] = backup_button.get("value", "")
            for hidden in form.find_all("input", type="hidden"):
                name = hidden.get("name")
                if name:
                    data[name] = hidden.get("value", "")
            async with self.session.post(post_url, data=data, timeout=self._timeout()) as response:
                if response.status != 200:
                    continue
                text = await response.text()
                content_type = response.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type and text:
                    return text
                if self._looks_like_config(text):
                    return text
        return None

    def _timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(total=self.timeout)

    def _extract_gambit(self, text: str) -> None:
        patterns = [
            r'name\s*=\s*["\']Gambit["\']\s+value\s*=\s*["\']([^"\']+)["\']',
            r'value\s*=\s*["\']([^"\']+)["\']\s+name\s*=\s*["\']Gambit["\']',
            r'Gambit["\s=:]+([A-F0-9a-f]{6,})',
            r'var\s+Gambit\s*=\s*["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                self.gambit_token = match.group(1)
                return

    def _extract_public_key(self, text: str) -> str | None:
        match = re.search(r"(-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----)", text, re.DOTALL)
        if not match:
            return None
        return match.group(1).replace("\\n", "\n").replace("\\", "").strip()

    def _find_backup_button(self, form) -> object | None:
        for button in form.find_all(["input", "button"]):
            name = button.get("name", "").lower()
            value = button.get("value", "").lower()
            text = button.get_text(" ").lower()
            if "backup" in name or value == "backup" or "backup" in text:
                return button
        return None

    def _has_failure_text(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in [
                "invalid",
                "fail",
                "error_msg = 'error",
                "wrong password",
            ]
        )

    def _looks_like_config(self, text: str) -> bool:
        prefix = text[:300].lower()
        return any(marker in prefix for marker in ["config", "sysname", "hostname", "interface"])
```

- [ ] **Step 2: Run WebSmart client tests**

```bash
rtk python -m pytest app_v4/tests/test_websmart_client.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit client**

```bash
rtk git add app_v4/net/websmart_client.py app_v4/tests/test_websmart_client.py
rtk git commit -m "feat: add async WebSmart backup client"
```

---

## Task 4: Extend backup runner for WebSmart protocols

**Files:**
- Modify: `app_v4/net/runner.py`
- Modify: `app_v4/tests/test_backup_runner.py`

- [ ] **Step 1: Update runner tests**

In `app_v4/tests/test_backup_runner.py`, replace the unsupported protocol test with this test:

```python
@pytest.mark.asyncio
async def test_backup_runner_rejects_unsupported_protocol():
    runner = BackupRunner(settings=Settings(), client_factory=lambda **kwargs: FakeClient("x"))

    result = await runner.execute_backup("snmp", "host", 161, "u", "p")

    assert result.success is False
    assert "Unsupported protocol" in result.message
```

Append this test to `app_v4/tests/test_backup_runner.py`:

```python
@pytest.mark.asyncio
async def test_backup_runner_accepts_websmart_protocol_from_client_factory():
    created = {}

    def factory(**kwargs):
        created.update(kwargs)
        return FakeClient("websmart config")

    runner = BackupRunner(
        settings=Settings(network_max_retries=1),
        client_factory=factory,
    )

    result = await runner.execute_backup("websmart", "10.0.0.10", 80, "admin", "secret")

    assert result.success is True
    assert result.config_text == "websmart config"
    assert created["protocol"] == "websmart"
    assert created["host"] == "10.0.0.10"
    assert created["port"] == 80
```

- [ ] **Step 2: Run runner tests to verify failure**

```bash
rtk python -m pytest app_v4/tests/test_backup_runner.py -v
```

Expected: FAIL because `websmart` is still unsupported.

- [ ] **Step 3: Update runner imports**

In `app_v4/net/runner.py`, add this import with the other client imports:

```python
from app_v4.net.websmart_client import AsyncWebSmartClient
```

- [ ] **Step 4: Update allowed protocols**

In `BackupRunner.execute_backup`, replace the Phase 1 protocol guard with this code:

```python
        protocol = protocol.lower()
        allowed_protocols = {"ssh", "telnet", "http", "https", "websmart", "websmart-v2"}
        if protocol not in allowed_protocols:
            return BackupRunResult(False, "", f"Unsupported protocol: {protocol}")
```

- [ ] **Step 5: Replace `_make_client`**

Replace the full `_make_client` method in `app_v4/net/runner.py` with this method:

```python
    def _make_client(self, protocol: str, host: str, port: int, username: str, password: str, enable_password: str) -> BackupClient:
        if self.client_factory is not None:
            return self.client_factory(
                protocol=protocol,
                host=host,
                port=port,
                username=username,
                password=password,
                enable_password=enable_password,
                timeout=self.config.connect_timeout,
            )
        if protocol == "ssh":
            return AsyncSshClient(host, port, username, password, enable_password, self.config.connect_timeout)
        if protocol == "telnet":
            return AsyncTelnetClient(host, port, username, password, enable_password, self.config.connect_timeout)
        scheme = "https" if protocol == "https" else "http"
        return AsyncWebSmartClient(
            host=host,
            port=port,
            username=username,
            password=password,
            timeout=self.config.connect_timeout,
            scheme=scheme,
            force_v2_only=protocol == "websmart-v2",
        )
```

- [ ] **Step 6: Run runner tests**

```bash
rtk python -m pytest app_v4/tests/test_backup_runner.py -v
```

Expected: PASS.

- [ ] **Step 7: Run WebSmart tests again**

```bash
rtk python -m pytest app_v4/tests/test_websmart_client.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit runner support**

```bash
rtk git add app_v4/net/runner.py app_v4/tests/test_backup_runner.py
rtk git commit -m "feat: route WebSmart protocols through v4 backup runner"
```

---

## Task 5: Verify WebSmart support through backup service path

**Files:**
- Modify: `app_v4/tests/test_backup_service.py`

- [ ] **Step 1: Add backup service WebSmart test**

Append this test to `app_v4/tests/test_backup_service.py`:

```python
@pytest.mark.asyncio
async def test_backup_service_runs_websmart_switch(test_settings, session_factory, crypto_service):
    calls = []

    @dataclass
    class RecordingRunner:
        result: BackupRunResult

        async def execute_backup(self, protocol, host, port, username, password, enable_password=""):
            calls.append((protocol, host, port, username, password, enable_password))
            return self.result

    service = BackupService(
        settings=test_settings,
        session_factory=session_factory,
        crypto_service=crypto_service,
        runner=RecordingRunner(BackupRunResult(True, "hostname websmart", "Backup completed successfully")),
        diff_service=DiffService(test_settings),
    )
    async with session_factory() as session:
        repo = Repository(session)
        blob = crypto_service.encrypt_credential("manager", "friend", "")
        cred = await repo.create_credential("web", blob)
        switch = await repo.create_switch("websw", "10.0.0.20", "websmart", 80, cred.id)
        await session.commit()
        switch_id = switch.id

    result = await service.execute_backup(switch_id=switch_id, backup_type="manual", triggered_by_user_id=None)

    assert result["success"] is True
    assert result["backup_id"] > 0
    assert calls == [("websmart", "10.0.0.20", 80, "manager", "friend", "")]
```

- [ ] **Step 2: Run backup service test**

```bash
rtk python -m pytest app_v4/tests/test_backup_service.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit service path coverage**

```bash
rtk git add app_v4/tests/test_backup_service.py
rtk git commit -m "test: cover WebSmart backup service path"
```

---

## Task 6: Final verification

**Files:**
- Verify all Phase 1 and Phase 2 v4 tests.

- [ ] **Step 1: Run focused execution tests**

```bash
rtk python -m pytest app_v4/tests/test_network_config.py app_v4/tests/test_backup_runner.py app_v4/tests/test_websmart_client.py app_v4/tests/test_backup_service.py app_v4/tests/test_backups_api.py app_v4/tests/test_jobs_api.py app_v4/tests/test_scheduler.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full v4 suite**

```bash
rtk python -m pytest app_v4/tests -v
```

Expected: PASS.

- [ ] **Step 3: Inspect git status**

```bash
rtk git status
```

Expected: only intentional tracked changes from Phase 2 remain staged or committed; no `app/` changes.

- [ ] **Step 4: Commit final verification marker if needed**

If Step 3 shows no uncommitted changes, do not create an empty commit.

If Step 3 shows intentional Phase 2 changes not yet committed, commit them:

```bash
rtk git add app_v4/requirements-v4.txt app_v4/net/websmart_client.py app_v4/net/runner.py app_v4/tests/test_websmart_client.py app_v4/tests/test_backup_runner.py app_v4/tests/test_backup_service.py
rtk git commit -m "feat: complete v4 WebSmart backup support"
```

---

## Self-Review

- Spec coverage: Phase 2 covers async-native WebSmart HTTP/HTTPS backup execution, traditional form-login WebSmart, WebSmart V2 RSA token login, runner protocol routing, and backup service execution path.
- Placeholder scan: No `TBD`, no `TODO`, no deferred implementation, no incomplete tests.
- Type consistency: `AsyncWebSmartClient` matches Phase 1 `BackupClient` protocol, `BackupRunner.execute_backup` still returns `BackupRunResult`, and `BackupService` continues to call the runner with switch protocol, host, port, username, password, and enable password.
