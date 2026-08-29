from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_v4.core.config import Settings
from app_v4.core.utcdatetime import utc_now
from app_v4.data.models import Switch
from app_v4.data.repository import Repository
from app_v4.net.config_parsers import parse_config
from app_v4.service.diff_service import DiffService

logger = logging.getLogger(__name__)

REVIEW_STATUSES = ("pending", "approved", "flagged", "dismissed")


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
    ):
        self.settings = settings
        self.session_factory = session_factory
        self._diff = DiffService(settings)

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

    async def compliance_summary(self, attestation_days: int = 30) -> dict:
        """ISO-friendly compliance snapshot: coverage, open reviews, stale baselines."""
        async with self.session_factory() as session:
            repo = Repository(session)
            switches = await repo.list_switches(include_inactive=False)
            total = len(switches)
            missing: list[str] = []
            stale: list[str] = []
            for sw in switches:
                baseline = await repo.get_baseline_for_switch(sw)
                if baseline is None:
                    missing.append(sw.name)
                    continue
                if baseline.created_at is None or (
                    (utc_now() - baseline.created_at).days > attestation_days
                ):
                    stale.append(sw.name)
            counts = await repo.count_reviews_by_status()
            return {
                "switches_total": total,
                "switches_with_baseline": total - len(missing),
                "switches_missing_baseline": missing,
                "baselines_stale": stale,
                "attestation_days": attestation_days,
                "reviews_pending": counts.get("pending", 0),
                "reviews_approved": counts.get("approved", 0),
                "reviews_flagged": counts.get("flagged", 0),
                "reviews_dismissed": counts.get("dismissed", 0),
            }

    async def send_reminder(self) -> dict[str, str]:
        """Build the review-reminder email body (subject, body) or empty strings.

        Called by the scheduler job; empty strings mean "nothing to send".
        """
        try:
            async with self.session_factory() as session:
                repo = Repository(session)
                pending = await repo.list_reviews(status="pending", limit=50)
                switches_missing = await repo.list_switches_missing_baseline()
                compliance = await self.compliance_summary()
            if not pending and not switches_missing:
                return {"subject": "", "body": ""}
            lines = [
                "Config management review reminder (ISO 27001 A.8.9)",
                "",
                f"Pending config reviews: {len(pending)}",
            ]
            for review in pending[:10]:
                lines.append(f"  - review #{review.id} (created {review.created_at:%Y-%m-%d %H:%M} UTC)")
            if len(pending) > 10:
                lines.append(f"  ... and {len(pending) - 10} more")
            if switches_missing:
                lines.append("")
                lines.append(f"Switches without a baseline: {len(switches_missing)}")
                for sw in switches_missing[:10]:
                    lines.append(f"  - {sw.name}")
            if compliance["baselines_stale"]:
                lines.append("")
                lines.append(f"Stale baselines (>{compliance['attestation_days']} days): {len(compliance['baselines_stale'])}")
                for name in compliance["baselines_stale"][:10]:
                    lines.append(f"  - {name}")
            lines.append("")
            lines.append("Review queue: {url}".format(url=""))  # URL added by caller (Notifier)
            return {"subject": f"[NCM] Config review: {len(pending)} pending", "body": "\n".join(lines)}
        except Exception:  # noqa: BLE001
            logger.exception("review reminder build failed")
            return {"subject": "", "body": ""}


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
