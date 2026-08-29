from __future__ import annotations

import json
import logging
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

from app_v4.core.runtime_settings import NotifySettings, load_runtime_settings

logger = logging.getLogger(__name__)


class NotifyResult:
    def __init__(self, ok: bool, channel: str, detail: str = "") -> None:
        self.ok = ok
        self.channel = channel
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"NotifyResult(ok={self.ok}, channel={self.channel!r}, detail={self.detail!r})"


def load_notify_settings(runtime_settings_path: Path) -> NotifySettings:
    return load_runtime_settings(runtime_settings_path).notify


class Notifier:
    """Outbound drift notifications + review reminders.

    Delivery is best-effort by design: a broken webhook or SMTP must never
    break the backup or review path, so every send failure is logged and
    returned instead of raised.
    """

    def __init__(self, runtime_settings_path: Path):
        self._runtime_settings_path = runtime_settings_path

    def settings(self) -> NotifySettings:
        return load_notify_settings(self._runtime_settings_path)

    # ----- channels -------------------------------------------------------

    async def webhook(self, payload: dict) -> NotifyResult:
        cfg = self.settings()
        if not cfg.enabled or not cfg.webhook_url:
            return NotifyResult(False, "webhook", "webhook disabled or url empty")
        return self._post_json(cfg.webhook_url, payload)

    def _post_json(self, url: str, payload: dict) -> NotifyResult:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return NotifyResult(200 <= response.status < 300, "webhook", f"status {response.status}")
        except urllib.error.HTTPError as exc:
            return NotifyResult(False, "webhook", f"http {exc.code}")
        except Exception as exc:  # noqa: BLE001 - best-effort channel
            logger.warning("webhook notify failed: %s", exc)
            return NotifyResult(False, "webhook", str(exc))

    async def email(self, subject: str, body: str, to: tuple[str, ...] | None = None) -> NotifyResult:
        cfg = self.settings()
        if not cfg.email_enabled or not cfg.smtp_host:
            return NotifyResult(False, "email", "email disabled or smtp host empty")
        recipients = to or cfg.email_to
        if not recipients:
            return NotifyResult(False, "email", "no recipients configured")
        try:
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = cfg.smtp_username or "ncm-v4@localhost"
            message["To"] = ", ".join(recipients)
            message.set_content(body)

            if cfg.smtp_tls:
                server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15)
                try:
                    server.starttls()
                    if cfg.smtp_username and cfg.smtp_password:
                        server.login(cfg.smtp_username, cfg.smtp_password)
                    server.send_message(message)
                finally:
                    server.quit()
            else:
                with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as server:
                    if cfg.smtp_username and cfg.smtp_password:
                        server.login(cfg.smtp_username, cfg.smtp_password)
                    server.send_message(message)
            return NotifyResult(True, "email", f"sent to {len(recipients)} recipient(s)")
        except Exception as exc:  # noqa: BLE001 - best-effort channel
            logger.warning("email notify failed: %s", exc)
            return NotifyResult(False, "email", str(exc))

    # ----- convenience ----------------------------------------------------

    def review_url(self) -> str:
        return f"{self.settings().app_public_url.rstrip('/')}/config-review"
