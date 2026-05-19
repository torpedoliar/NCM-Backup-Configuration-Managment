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
