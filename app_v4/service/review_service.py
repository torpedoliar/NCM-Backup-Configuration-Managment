from __future__ import annotations

import calendar
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.core.utcdatetime import utc_now
from app_v4.data.models import Switch
from app_v4.data.repository import Repository
from app_v4.net.config_parsers import parse_config
from app_v4.service.diff_service import DiffService

logger = logging.getLogger(__name__)

REVIEW_STATUSES = ("pending", "approved", "flagged", "dismissed")


def _add_months(moment: datetime, months: int) -> datetime:
    """Naive-UTC datetime plus N calendar months (clamped to month end)."""
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def _render_reminder_template(template: str, ctx: dict, review_url: str) -> str:
    """Fill a user HTML template with reminder variables.

    Supported: {{pending_count}}, {{pending_reviews_html}}, {{missing_count}},
    {{missing_baselines}}, {{stale_count}}, {{stale_baselines}},
    {{reviews_flagged}}, {{total_switches}}, {{baseline_coverage}},
    {{review_url}}, {{generated_at}}. Values are HTML-escaped; the table-row
    block is pre-built HTML. Unknown variables render as empty string.
    """
    import html as html_mod

    def esc(value) -> str:
        return html_mod.escape(str(value))

    rows = "".join(
        f"<tr><td>#{r['id']}</td><td>{esc(r['switch'])}</td><td>{esc(r['created'])}</td></tr>"
        for r in ctx["pending_reviews"]
    ) or '<tr><td colspan="3">No pending reviews</td></tr>'
    reminder_rows = "".join(
        f"<tr><td>{esc(r['switch'])}</td><td>{esc(r['due_at'])}</td><td>{esc(r['days_overdue'])}</td></tr>"
        for r in ctx.get("reminder_reviews", [])
    ) or '<tr><td colspan="3">None due</td></tr>'
    values = {
        "pending_count": ctx["pending_count"],
        "pending_reviews_html": rows,
        "missing_count": ctx["missing_count"],
        "missing_baselines": esc(", ".join(ctx["missing_baselines"])),
        "stale_count": ctx["stale_count"],
        "stale_baselines": esc(", ".join(ctx["stale_baselines"])),
        "reminder_review_count": ctx.get("reminder_review_count", 0),
        "reminder_reviews_html": reminder_rows,
        "review_interval_months": ctx.get("review_interval_months", 6),
        "reviews_flagged": ctx["reviews_flagged"],
        "total_switches": ctx["total_switches"],
        "baseline_coverage": ctx["baseline_coverage"],
        "review_url": esc(review_url),
        "generated_at": esc(utc_now().strftime("%Y-%m-%d %H:%M UTC")),
    }
    out = template
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", str(val))
    # Unknown variables render as empty string, not literal {{...}}.
    return re.sub(r"\{\{\s*[a-z_]+\s*\}\}", "", out)


def _default_reminder_text(ctx: dict, review_url: str) -> str:
    """Plain-text fallback of the reminder (multipart email text part)."""
    lines = [
        "Config management review reminder (ISO 27001 A.8.9)",
        "",
        f"Pending config reviews: {ctx['pending_count']}",
    ]
    for r in ctx["pending_reviews"][:10]:
        lines.append(f"  - review #{r['id']} (created {r['created']} UTC)")
    if ctx["pending_count"] > 10:
        lines.append(f"  ... and {ctx['pending_count'] - 10} more")
    if ctx["missing_count"]:
        lines.append("")
        lines.append(f"Switches without a baseline: {ctx['missing_count']}")
        for name in ctx["missing_baselines"][:10]:
            lines.append(f"  - {name}")
    if ctx["stale_count"]:
        lines.append("")
        lines.append(f"Stale baselines (>30 days): {ctx['stale_count']}")
        for name in ctx["stale_baselines"][:10]:
            lines.append(f"  - {name}")
    if ctx.get("reminder_review_count"):
        lines.append("")
        lines.append(
            f"Reminder review (every {ctx.get('review_interval_months', 6)} months): "
            f"{ctx['reminder_review_count']} baseline(s) due"
        )
        for r in ctx.get("reminder_reviews", [])[:10]:
            overdue = f", {r['days_overdue']} days overdue" if r["days_overdue"] else ""
            lines.append(f"  - {r['switch']} (due {r['due_at']}{overdue})")
    if review_url:
        lines.append("")
        lines.append(f"Review queue: {review_url}")
    return "\n".join(lines)


DEFAULT_REMINDER_HTML = """\
<h2>Config management review reminder</h2>
<p>ISO 27001 A.8.9 &mdash; configuration management status as of {{generated_at}}.</p>
<h3>Pending config reviews: {{pending_count}}</h3>
<table border="1" cellpadding="4" cellspacing="0">
  <thead><tr><th>ID</th><th>Switch</th><th>Created</th></tr></thead>
  <tbody>
{{pending_reviews_html}}
  </tbody>
</table>
<h3>Baseline coverage</h3>
<p>{{baseline_coverage}}% of {{total_switches}} switches covered.</p>
<h3>Missing baselines: {{missing_count}}</h3>
<p>{{missing_baselines}}</p>
<h3>Stale baselines (&gt;30 days): {{stale_count}}</h3>
<p>{{stale_baselines}}</p>
<h3>Reminder review (every {{review_interval_months}} months): {{reminder_review_count}}</h3>
<table border="1" cellpadding="4" cellspacing="0">
  <thead><tr><th>Switch</th><th>Due</th><th>Days overdue</th></tr></thead>
  <tbody>
{{reminder_reviews_html}}
  </tbody>
</table>
<p><a href="{{review_url}}">Open the review queue</a></p>
"""


@dataclass(frozen=True)
class DriftOutcome:
    review_id: int | None
    drifted: bool
    reason: str = ""


class ReviewService:
    """Baseline matching + config-change review logging (ISO 27001 A.8.9 evidence).

    Non-blocking by contract: ``on_backup_complete`` is called from the backup
    path, so all of its own errors are swallowed and logged — a review-pipeline
    failure must never fail a backup.
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        notifier=None,
        email_template: str = "",
    ):
        self.settings = settings
        self.session_factory = session_factory
        self._diff = DiffService(settings)
        self.notifier = notifier
        self._email_template = email_template

    async def on_backup_complete(
        self,
        switch: Switch,
        backup_id: int,
        content_text: str,
        baseline_text: str | None,
        baseline_id: int | None,
    ) -> DriftOutcome:
        """Create a pending review when the new config differs from the baseline.

        ``baseline_text``/``baseline_id`` come from the caller (backup_service),
        which already resolved the applicable baseline for this switch.
        """
        try:
            if baseline_text is None:
                return DriftOutcome(None, False, "no baseline")
            raw_diff = self._diff.unified_diff(baseline_text, content_text, "Baseline", "Current")
            if not raw_diff.strip():
                return DriftOutcome(None, False, "no diff")
            summary = self._structured_summary(baseline_text, content_text)
            async with self.session_factory() as session:
                repo = Repository(session)
                review = await repo.create_review(
                    switch_id=switch.id,
                    backup_id=backup_id,
                    baseline_id=baseline_id,
                    raw_diff=raw_diff,
                    diff_summary=json.dumps(summary),
                )
                await session.commit()
            if self.notifier is not None:
                # Best-effort drift alerts (Telegram + email); never raises.
                try:
                    await self.notifier.telegram(
                        f"Config drift on {switch.name} (backup #{backup_id}, review #{review.id}): "
                        f"{json.dumps(summary)}"
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("telegram drift alert failed", exc_info=True)
                try:
                    from app_v4.core.runtime_settings import load_runtime_settings
                    from app_v4.core.paths import resolve_paths
                    from app_v4.service import email_events

                    paths = resolve_paths(self.settings)
                    cfg = load_runtime_settings(paths.data_dir / "runtime_settings.json").notify
                    summary_text = "; ".join(
                        f"{k.replace('_', ' ')}: {v}" for k, v in summary.items() if v
                    ) or "text diff"
                    if cfg.enabled and cfg.email_enabled and cfg.email_review_events:
                        content = email_events.review_opened_email(
                            switch.name, review.id, summary_text, self._review_url(cfg)
                        )
                        await self.notifier.email(
                            content["subject"], content["body_text"], body_html=content["body_html"]
                        )
                except Exception:  # noqa: BLE001
                    logger.warning("review-opened email failed", exc_info=True)
            return DriftOutcome(review.id, True)
        except Exception:  # noqa: BLE001 - review must never break backups
            logger.exception("config review pipeline failed for switch %s", switch.id)
            return DriftOutcome(None, False, "review pipeline error")

    @staticmethod
    def _structured_summary(baseline_text: str, current_text: str) -> dict:
        """Human-readable structured delta: VLANs and port state changes."""
        base = parse_config(baseline_text)
        cur = parse_config(current_text)
        base_vlans = {v.id: v.name for v in base.vlans}
        cur_vlans = {v.id: v.name for v in cur.vlans}

        def _port_key(p) -> tuple:
            return (p.mode, p.native_vlan, p.access_vlan, tuple(p.trunk_allowed_vlans))

        base_ports = {p.name: _port_key(p) for p in base.ports}
        cur_ports = {p.name: _port_key(p) for p in cur.ports}

        ports_changed = sorted(
            name for name in (set(base_ports) & set(cur_ports)) if base_ports[name] != cur_ports[name]
        )
        return {
            "vlans_added": sorted(set(cur_vlans) - set(base_vlans)),
            "vlans_removed": sorted(set(base_vlans) - set(cur_vlans)),
            "vlans_renamed": sorted(
                v for v in (set(base_vlans) & set(cur_vlans)) if base_vlans[v] != cur_vlans[v]
            ),
            "ports_added": sorted(set(cur_ports) - set(base_ports)),
            "ports_removed": sorted(set(base_ports) - set(cur_ports)),
            "ports_changed": ports_changed,
            "hostname_changed": base.hostname != cur.hostname,
        }

    async def set_review_status(
        self,
        review_id: int,
        status: str,
        reviewed_by: int | None,
        comment: str | None = None,
    ) -> bool:
        if status not in REVIEW_STATUSES:
            raise ValueError(f"invalid review status: {status}")
        async with self.session_factory() as session:
            repo = Repository(session)
            review = await repo.update_review(
                review_id, status=status, reviewed_by=reviewed_by, comment=comment
            )
            await session.commit()
            return review is not None

    def _interval_months(self) -> int:
        """Configured review cycle length in months (runtime settings, default 6)."""
        try:
            from app_v4.core.runtime_settings import load_runtime_settings

            months = int(self.settings.review_interval_months)
            return max(1, months)
        except AttributeError:
            return 6

    @staticmethod
    def _review_url(cfg) -> str:
        return f"{cfg.app_public_url.rstrip('/')}/config-review"

    async def compliance_summary(self, attestation_days: int | None = None) -> dict:
        """ISO-friendly compliance snapshot: coverage, open reviews, reminder-review status.

        Staleness uses exact calendar months: a baseline is due when
        ``now >= created_at + review_interval_months`` (not a 30-day
        approximation). ``attestation_days`` is kept for callers that pass it
        explicitly; the default is derived from the interval.
        """
        interval_months = self._interval_months()
        if attestation_days is None:
            attestation_days = interval_months * 30  # legacy field; display only
        now = utc_now()
        async with self.session_factory() as session:
            repo = Repository(session)
            switches = await repo.list_switches(include_inactive=False)
            total = len(switches)
            missing: list[str] = []
            stale: list[str] = []
            reminder_due: list[str] = []
            for sw in switches:
                baseline = await repo.get_baseline_for_switch(sw)
                if baseline is None:
                    missing.append(sw.name)
                    continue
                if baseline.created_at is None or now >= _add_months(
                    baseline.created_at, interval_months
                ):
                    stale.append(sw.name)
                    reminder_due.append(sw.name)
            counts = await repo.count_reviews_by_status()
            return {
                "switches_total": total,
                "switches_with_baseline": total - len(missing),
                "switches_missing_baseline": missing,
                "baselines_stale": stale,
                "reminder_due": reminder_due,
                "attestation_days": attestation_days,
                "review_interval_months": interval_months,
                "reviews_pending": counts.get("pending", 0),
                "reviews_approved": counts.get("approved", 0),
                "reviews_flagged": counts.get("flagged", 0),
                "reviews_dismissed": counts.get("dismissed", 0),
            }

    async def compliance_rows(self) -> list[dict]:
        """Per-switch compliance rows for report export (ISO 27001 A.8.9)."""
        interval_months = self._interval_months()
        now = utc_now()
        rows: list[dict] = []
        async with self.session_factory() as session:
            repo = Repository(session)
            switches = await repo.list_switches(include_inactive=False)
            for sw in switches:
                baseline = await repo.get_baseline_for_switch(sw)
                baseline_state = "no"
                next_review = ""
                reminder_due = False
                if baseline is not None:
                    baseline_state = "yes"
                    if baseline.created_at is not None:
                        due_at = _add_months(baseline.created_at, interval_months)
                        next_review = due_at.strftime("%Y-%m-%d")
                        reminder_due = now >= due_at
                        if reminder_due:
                            baseline_state = "stale"
                latest = await repo.get_latest_backup(sw.id)
                reviews = await repo.list_reviews(switch_id=sw.id, limit=1)
                last_review = reviews[0] if reviews else None
                pending_count = len(await repo.list_reviews(status="pending", switch_id=sw.id, limit=200))
                rows.append(
                    {
                        "switch": sw.name,
                        "ip": sw.ip,
                        "model": sw.model or "",
                        "baseline": baseline_state,
                        "last_backup": latest.taken_at.strftime("%Y-%m-%d %H:%M:%S")
                        if latest and latest.taken_at
                        else "",
                        "open_reviews": pending_count,
                        "last_review": last_review.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if last_review and last_review.created_at
                        else "",
                        "review_state": last_review.status if last_review else "",
                        "next_review": next_review,
                        "reminder_due": reminder_due,
                    }
                )
        return rows

    async def reminder_context(self) -> dict:
        """Gather the reminder data into a plain dict (template variables)."""
        async with self.session_factory() as session:
            repo = Repository(session)
            pending = await repo.list_reviews(status="pending", limit=50)
            switches_missing = await repo.list_switches_missing_baseline()
            compliance = await self.compliance_summary()

        name_by_id: dict[int, str] = {}
        async with self.session_factory() as session:
            repo = Repository(session)
            for review in pending:
                if review.switch_id not in name_by_id:
                    sw = await repo.get_switch(review.switch_id)
                    if sw is not None:
                        name_by_id[review.switch_id] = sw.name

        pending_rows = [
            {
                "id": r.id,
                "switch": name_by_id.get(r.switch_id, f"#{r.switch_id}"),
                "created": (r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""),
            }
            for r in pending
        ]
        interval_months = self._interval_months()
        window_days = interval_months * 30
        now = utc_now()
        reminder_rows: list[dict] = []
        async with self.session_factory() as session:
            repo = Repository(session)
            for sw in await repo.list_switches(include_inactive=False):
                baseline = await repo.get_baseline_for_switch(sw)
                if baseline is None or baseline.created_at is None:
                    continue
                due_at = _add_months(baseline.created_at, interval_months)
                if now >= due_at:
                    reminder_rows.append(
                        {
                            "switch": sw.name,
                            "due_at": due_at.strftime("%Y-%m-%d"),
                            "days_overdue": (now - due_at).days,
                            "interval_months": interval_months,
                        }
                    )
        return {
            "pending_count": len(pending_rows),
            "pending_reviews": pending_rows,
            "missing_count": len(switches_missing),
            "missing_baselines": [sw.name for sw in switches_missing],
            "stale_baselines": list(compliance.get("baselines_stale", [])),
            "stale_count": len(compliance.get("baselines_stale", [])),
            "reminder_reviews": reminder_rows,
            "reminder_review_count": len(reminder_rows),
            "review_interval_months": interval_months,
            "reviews_flagged": compliance.get("reviews_flagged", 0),
            "total_switches": compliance.get("switches_total", 0),
            "baseline_coverage": (
                round(100 * compliance.get("switches_with_baseline", 0) / compliance["switches_total"])
                if compliance.get("switches_total")
                else 0
            ),
        }

    async def send_reminder(self, review_url: str = "") -> dict[str, str]:
        """Build the review-reminder email (subject, body_html, body_text) or empty strings.

        ``review_url`` is the public review-queue link inserted into the body.
        Renders a user-editable HTML template when one is configured
        (runtime settings ``notify.email_template``), falling back to the
        built-in default. Empty strings returned mean "nothing to send".
        """
        try:
            ctx = await self.reminder_context()
            if not (
                ctx["pending_count"] or ctx["missing_count"] or ctx.get("reminder_review_count")
            ):
                return {"subject": "", "body_html": "", "body_text": ""}
            if not self._email_template:
                subject = f"[NCM] Config review: {ctx['pending_count']} pending"
                return {"subject": subject, "body_html": DEFAULT_REMINDER_HTML, "body_text": _default_reminder_text(ctx, review_url)}
            template = self._email_template
            if not template.strip():
                subject = f"[NCM] Config review: {ctx['pending_count']} pending"
                return {"subject": subject, "body_html": DEFAULT_REMINDER_HTML, "body_text": _default_reminder_text(ctx, review_url)}
            rendered = _render_reminder_template(template, ctx, review_url)
            subject = f"[NCM] Config review: {ctx['pending_count']} pending"
            return {"subject": subject, "body_html": rendered, "body_text": _default_reminder_text(ctx, review_url)}
        except Exception:  # noqa: BLE001
            logger.exception("review reminder build failed")
            return {"subject": "", "body_html": "", "body_text": ""}
