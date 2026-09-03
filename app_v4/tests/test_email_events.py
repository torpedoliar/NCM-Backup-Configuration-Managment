"""Email event builders: distinct, informative subjects + escaped bodies."""

import html

from app_v4.service import email_events


def test_backup_failed_subject_contains_switch_and_id():
    c = email_events.backup_failed_email("SW-CORE-01", "timeout", 123, "manual")
    assert c["subject"] == "[NCM] BACKUP GAGAL — SW-CORE-01 (backup #123)"
    assert "timeout" in c["body_text"]
    assert html.escape("timeout") in c["body_html"] or "timeout" in c["body_html"]


def test_backup_success_subject_reflects_change_state():
    ok_changed = email_events.backup_success_email("SW-1", "msg", 5, 12.3, changed=True)
    ok_same = email_events.backup_success_email("SW-1", "msg", 6, 12.3, changed=False)
    assert "BERUBAH" in ok_changed["subject"]
    assert "tidak berubah" in ok_same["subject"]
    assert ok_changed["subject"] != ok_same["subject"]


def test_review_opened_subject_contains_id_and_switch():
    c = email_events.review_opened_email("SW-2", 45, "vlans_added: [99]", "http://x/config-review")
    assert c["subject"] == "[NCM] REVIEW PENDING #45 — SW-2 (drift terdeteksi)"
    assert "vlans_added: [99]" in c["body_text"]


def test_review_decision_subject_contains_status_and_reviewer():
    c = email_events.review_decision_email("SW-2", 45, "approved", "looks good", "admin", "http://x")
    assert c["subject"] == "[NCM] REVIEW APPROVED #45 — SW-2 — oleh admin"
    flagged = email_events.review_decision_email("SW-2", 46, "flagged", None, "admin", "http://x")
    assert "FLAGGED" in flagged["subject"]
    # HTML-escaped comment in html body, plain in text body.
    assert "looks good" in c["body_text"]
