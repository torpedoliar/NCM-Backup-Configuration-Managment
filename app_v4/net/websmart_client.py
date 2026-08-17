from __future__ import annotations

import base64
import codecs
import json
import re
import time
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
        timeout: float = 30,
        scheme: str = "http",
        force_v2_only: bool = False,
        session: aiohttp.ClientSession | None = None,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        command_timeout: float | None = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.connect_timeout = connect_timeout if connect_timeout is not None else timeout
        self.read_timeout = read_timeout if read_timeout is not None else timeout
        self.command_timeout = command_timeout if command_timeout is not None else timeout
        self.scheme = scheme
        self.base_url = f"{scheme}://{host}:{port}/"
        self.force_v2_only = force_v2_only
        self.gambit_token: str | None = None
        self.is_v2_model = False
        self._operation_deadline: float | None = None
        self._owns_session = session is None
        self.session = session or aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

    async def connect(self) -> bool:
        self._operation_deadline = time.monotonic() + self.command_timeout
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
        # Traditional and V2 firmware both expose at least one of these
        # session-authenticated paths. Keep both bare fallbacks for older
        # WebSmart models that do not require the Gambit query parameter.
        endpoints.extend(["iss1.conf", "iss.conf"])
        endpoints.extend(
            [
                "iss/config_file_http.html",
                "config.bin",
                "backup.cgi",
                "config/backup.cgi",
                "system/config_backup.htm",
                "maintenance/upload_download.htm",
            ]
        )

        last_url = self.base_url
        successful_endpoint_paths: set[str] = set()
        for endpoint in endpoints:
            endpoint_path = endpoint.split("?", 1)[0]
            if "?" not in endpoint and endpoint_path in successful_endpoint_paths:
                continue
            last_url = urljoin(self.base_url, endpoint)
            try:
                async with self.session.get(last_url, timeout=self._timeout()) as response:
                    content_type = response.headers.get("Content-Type", "").lower()
                    payload, text = await self._read_response_text(response)
                    if response.status != 200:
                        continue
                    successful_endpoint_paths.add(endpoint_path)
                    if self._is_config_payload(payload, text, content_type):
                        return text
                    if endpoint == "iss/config_file_http.html" and "text/html" in content_type:
                        form_result = await self._submit_backup_form(last_url, text)
                        if form_result:
                            return form_result
            except (aiohttp.ClientError, UnicodeError, LookupError):
                # A firmware endpoint can return a binary or malformed body.
                # Treat that endpoint as unsupported and continue probing the
                # remaining known paths instead of aborting the whole backup.
                continue

        raise ValueError(f"Could not find a valid configuration download endpoint from {last_url}")

    async def disconnect(self) -> None:
        try:
            await self.session.get(urljoin(self.base_url, "logout.cgi"), timeout=aiohttp.ClientTimeout(total=5))
        except Exception:
            pass
        if self._owns_session:
            await self.session.close()
        self._operation_deadline = None

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
                    allow_redirects=False,
                ) as response:
                    _, text = await self._read_response_text(response)
                    if response.status not in (200, 301, 302, 303, 307, 308):
                        continue
                    self._extract_gambit(text)
                    response_url = str(response.url).lower()
                    if self.gambit_token:
                        return True

                    if response.status in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location:
                            continue
                        landing_url = urljoin(target_url, location)
                        async with self.session.get(
                            landing_url,
                            timeout=self._timeout(),
                            allow_redirects=False,
                        ) as landing:
                            _, landing_text = await self._read_response_text(landing)
                            self._extract_gambit(landing_text)
                            if self.gambit_token:
                                return True
                            landing_url_text = str(landing.url).lower()
                            if (
                                landing.status == 200
                                and "login" not in landing_url_text
                                and "logon" not in landing_url_text
                                and not self._has_failure_text(landing_text)
                                and not self._looks_like_login_page(landing_text)
                            ):
                                return True
                        continue

                    if "login" not in response_url and "logon" not in response_url:
                        return True
                    if "iss/" in response_url:
                        return True
                    if not self._has_failure_text(text):
                        return True
            except (aiohttp.ClientError, UnicodeError, LookupError):
                continue
        raise ConnectionError("Failed to login to WebSmart switch. Check credentials or network.")

    async def _try_v2_login(self) -> bool:
        try:
            pubkey_url = urljoin(self.base_url, "iss/specific/web_pub_key_data.js")
            async with self.session.get(pubkey_url, timeout=self._timeout()) as response:
                if response.status != 200:
                    return False
                _, pubkey_text = await self._read_response_text(response)
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

            self.session.headers.update(
                {
                    "Accept": "application/json, text/plain, */*",
                    "Referer": urljoin(self.base_url, "main.html"),
                }
            )
            login_url = urljoin(self.base_url, "iss/specific/web_login_data.js")
            async with self.session.get(
                login_url,
                params={"pelican": pelican, "pinkpanther": pinkpanther},
                timeout=self._timeout(),
            ) as response:
                if response.status != 200:
                    return False
                _, body = await self._read_response_text(response)
            data = json.loads(body)
            gambit = data.get("gambit")
            if not isinstance(gambit, str) or not gambit:
                return False
            self.gambit_token = gambit
            self.is_v2_model = True
            return True
        except (aiohttp.ClientError, ValueError, TypeError, json.JSONDecodeError, UnicodeError, LookupError):
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
                payload, text = await self._read_response_text(response)
                content_type = response.headers.get("Content-Type", "").lower()
                if self._is_config_payload(payload, text, content_type):
                    return text
                if (
                    "text/html" not in content_type
                    and "\ufffd" not in text
                    and "\x00" not in text
                    and self._looks_like_config(text)
                    and not self._looks_like_login_page(text)
                    and not self._has_failure_text(text)
                ):
                    return text
        return None

    async def _read_response_text(self, response) -> tuple[bytes, str]:
        payload = await response.read()
        return payload, self._decode_response_payload(payload, response.charset)

    def _decode_response_payload(self, payload: bytes, declared_encoding: str | None) -> str:
        """Decode legacy switch responses without allowing a codec error to escape.

        WebSmart firmware is inconsistent about Content-Type charset headers. Prefer
        BOM-detected Unicode and the advertised charset, then try the common legacy
        text encodings used by network equipment. Binary or malformed responses are
        still rejected later by the configuration validators.
        """
        encodings: list[str] = []
        if payload.startswith(codecs.BOM_UTF8):
            encodings.append("utf-8-sig")
        elif payload.startswith(codecs.BOM_UTF16_LE) or payload.startswith(codecs.BOM_UTF16_BE):
            encodings.append("utf-16")
        elif payload.startswith(codecs.BOM_UTF32_LE) or payload.startswith(codecs.BOM_UTF32_BE):
            encodings.append("utf-32")
        if declared_encoding:
            encodings.append(declared_encoding)
        encodings.extend(("utf-8", "cp1252", "latin-1"))

        for encoding in dict.fromkeys(encodings):
            try:
                return payload.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        return payload.decode("utf-8", errors="replace")

    def _is_config_payload(self, payload: bytes, text: str, content_type: str) -> bool:
        if not payload or "text/html" in content_type:
            return False
        if not text.strip() or b"\x00" in payload[:4096]:
            return False
        sample = text[:4000].lower()
        if "\ufffd" in sample:
            return False
        if self._looks_like_login_page(text) or self._has_failure_text(text):
            return False
        if any(marker in sample[:1000] for marker in ("<html", "<!doctype", "unauthorized", "forbidden", "not found")):
            return False
        return self._looks_like_config(text)

    def _timeout(self) -> aiohttp.ClientTimeout:
        configured_total = max(0.1, float(self.command_timeout))
        if self._operation_deadline is None:
            remaining = configured_total
        else:
            remaining = self._operation_deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("WebSmart backup command timeout exceeded")
        total = min(configured_total, remaining)
        return aiohttp.ClientTimeout(
            total=total,
            connect=min(total, max(0.1, float(self.connect_timeout))),
            sock_read=min(total, max(0.1, float(self.read_timeout))),
        )

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

    def _looks_like_login_page(self, text: str) -> bool:
        sample = text[:4000].lower()
        return ("login" in sample or "logon" in sample) and not self._looks_like_config(text)

    def _has_failure_text(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in [
                "invalid",
                "failed",
                "error:",
                "error_msg = 'error",
                "wrong password",
                "authentication failed",
                "unauthorized",
                "forbidden",
                "not found",
            ]
        )

    def _looks_like_config(self, text: str) -> bool:
        sample = text[:4000]
        structural_patterns = (
            r"^\s*(?:!|#\s*)?(?:sysname|hostname)\b",
            r"^\s*(?:interface|vlan|ip\s+address|ipv6\s+address)\b",
            r"^\s*(?:switchport|spanning-tree|bridge|router|snmp-server)\b",
            r"^\s*(?:username|enable\s+password|line\s+(?:vty|console))\b",
            r"^\s*(?:terminal\s+(?:length|pager)|no\s+page)\b",
        )
        if any(re.search(pattern, sample, re.IGNORECASE | re.MULTILINE) for pattern in structural_patterns):
            return True
        lines = [line.strip() for line in sample.splitlines() if line.strip()]
        return len(lines) >= 4 and any(line.startswith(("!", "#")) for line in lines)
