"""Email notifications for backup and review events (distinct, informative subjects).

Design: a notification failure must never break the triggering flow, so senders
are best-effort — every exception is swallowed and logged by the calling path.
"""

from __future__ import annotations

import html
import logging

from app_v4.core.utcdatetime import utc_now

logger = logging.getLogger(__name__)


def _fmt_dt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "-"


def backup_failed_email(switch_name: str, message: str, backup_id: int, backup_type: str) -> dict:
    """Subject: [NCM] BACKUP GAGAL — SW-CORE-01 (backup #123)."""
    return {
        "subject": f"[NCM] BACKUP GAGAL — {switch_name} (backup #{backup_id})",
        "body_text": (
            f"Backup {backup_type} untuk switch {switch_name} GAGAL.\n\n"
            f"Backup ID: #{backup_id}\n"
            f"Waktu: {_fmt_dt(utc_now())}\n"
            f"Pesan: {message}\n\n"
            f"Cek detail di halaman History."
        ),
        "body_html": (
            f"<h2 style='color:#c0392b'>Backup GAGAL — {html.escape(switch_name)}</h2>"
            f"<p>Backup tipe <b>{html.escape(backup_type)}</b> gagal pada {_fmt_dt(utc_now())}.</p>"
            f"<table border='1' cellpadding='6'><tr><th>Backup</th><td>#{backup_id}</td></tr>"
            f"<tr><th>Pesan</th><td>{html.escape(message)}</td></tr></table>"
            "<p>Cek detail di halaman History.</p>"
        ),
    }


def backup_success_email(
    switch_name: str, message: str, backup_id: int, size_kb: float, changed: bool
) -> dict:
    """Subject: [NCM] BACKUP OK — SW-CORE-01 (backup #124) — config BERUBAH / tidak berubah."""
    state = "config BERUBAH" if changed else "config tidak berubah"
    return {
        "subject": f"[NCM] BACKUP OK — {switch_name} (backup #{backup_id}) — {state}",
        "body_text": (
            f"Backup untuk switch {switch_name} BERHASIL ({state}).\n\n"
            f"Backup ID: #{backup_id}\n"
            f"Ukuran: {size_kb:.1f} KB\n"
            f"Waktu: {_fmt_dt(utc_now())}\n"
            f"Pesan: {message}\n"
        ),
        "body_html": (
            f"<h2 style='color:#1e8449'>Backup OK — {html.escape(switch_name)}</h2>"
            f"<p>Status: <b>{state}</b>.</p>"
            f"<table border='1' cellpadding='6'>"
            f"<tr><th>Backup</th><td>#{backup_id}</td></tr>"
            f"<tr><th>Ukuran</th><td>{size_kb:.1f} KB</td></tr>"
            f"<tr><th>Pesan</th><td>{html.escape(message)}</td></tr>"
            f"</table>"
        ),
    }


def review_opened_email(switch_name: str, review_id: int, summary_text: str, review_url: str) -> dict:
    """Subject: [NCM] REVIEW PENDING #45 — SW-CORE-01 (drift terdeteksi)."""
    return {
        "subject": f"[NCM] REVIEW PENDING #{review_id} — {switch_name} (drift terdeteksi)",
        "body_text": (
            f"Review baru #{review_id} untuk switch {switch_name} menunggu keputusan.\n\n"
            f"Ringkasan perubahan: {summary_text}\n"
            f"Waktu: {_fmt_dt(utc_now())}\n\n"
            f"Buka: {review_url}"
        ),
        "body_html": (
            f"<h2>Review PENDING #{review_id} — {html.escape(switch_name)}</h2>"
            f"<p>Drift dari baseline terdeteksi dan menunggu keputusan Anda.</p>"
            f"<p><b>Ringkasan:</b> {html.escape(summary_text)}</p>"
            f"<p><a href='{html.escape(review_url)}'>Buka halaman Config Review</a></p>"
        ),
    }


def review_decision_email(
    switch_name: str, review_id: int, status: str, comment: str | None, reviewer: str, review_url: str
) -> dict:
    """Subject: [NCM] REVIEW APPROVED #45 — SW-CORE-01 — oleh admin."""
    label = {
        "approved": "APPROVED",
        "flagged": "FLAGGED",
        "dismissed": "DISMISSED",
    }.get(status, status.upper())
    comment_html = (
        f"<p><b>Komentar:</b> {html.escape(comment)}</p>" if comment else ""
    )
    comment_text = f"\nKomentar: {comment}" if comment else ""
    return {
        "subject": f"[NCM] REVIEW {label} #{review_id} — {switch_name} — oleh {reviewer}",
        "body_text": (
            f"Review #{review_id} untuk switch {switch_name} telah diputuskan: {label}.\n"
            f"Reviewer: {reviewer}\n"
            f"Waktu: {_fmt_dt(utc_now())}{comment_text}\n\n"
            f"Buka: {review_url}"
        ),
        "body_html": (
            f"<h2>Review {label} #{review_id} — {html.escape(switch_name)}</h2>"
            f"<p>Keputusan: <b>{label}</b> oleh {html.escape(reviewer)} pada {_fmt_dt(utc_now())}.</p>"
            f"{comment_html}"
            f"<p><a href='{html.escape(review_url)}'>Buka halaman Config Review</a></p>"
        ),
    }
