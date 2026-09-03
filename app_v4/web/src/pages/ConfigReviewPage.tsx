import { useEffect, useState } from 'react';
import {
  downloadComplianceReport,
  fetchReviewDiff,
  useCompliance,
  useReviews,
  useReviewStatus,
} from '../api/hooks';
import type { ConfigReviewStatus, ReviewFilters } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';
import { humanizeError } from '../lib/errors';

const STATUS_LABEL: Record<string, string> = {
  pending: 'PENDING',
  approved: 'APPROVED',
  flagged: 'FLAGGED',
  dismissed: 'DISMISSED',
};

function summaryText(summary: Record<string, unknown>): string {
  const parts: string[] = [];
  const added = summary.vlans_added as number[] | undefined;
  const removed = summary.vlans_removed as number[] | undefined;
  const changed = summary.ports_changed as string[] | undefined;
  if (added?.length) parts.push(`VLAN +${added.join(',')}`);
  if (removed?.length) parts.push(`VLAN -${removed.join(',')}`);
  if (changed?.length) parts.push(`${changed.length} port(s) changed (${changed.slice(0, 5).join(', ')})`);
  if (summary.hostname_changed) parts.push('hostname changed');
  return parts.join(' · ') || 'text diff only';
}

function CompliancePanel() {
  const { data } = useCompliance();
  if (!data) return null;
  const coverage =
    data.switches_total > 0
      ? Math.round((data.switches_with_baseline / data.switches_total) * 100)
      : 0;
  return (
    <section className="settings-card">
      <h3>Compliance overview (ISO 27001 A.8.9)</h3>
      <p className="settings-help">
        Every switch needs a golden-config baseline; every drift from that baseline needs a review.
        This is the evidence trail for configuration management.
      </p>
      <div className="compliance-stats">
        <div>
          <span className="compliance-num">{coverage}%</span>
          <span className="compliance-label">baseline coverage</span>
        </div>
        <div>
          <span className="compliance-num">{data.reviews_pending}</span>
          <span className="compliance-label">reviews pending</span>
        </div>
        <div>
          <span className="compliance-num">{data.reviews_flagged}</span>
          <span className="compliance-label">flagged</span>
        </div>
        <div>
          <span className="compliance-num">{data.switches_missing_baseline.length}</span>
          <span className="compliance-label">switches without baseline</span>
        </div>
        <div>
          <span className="compliance-num">{data.baselines_stale.length}</span>
          <span className="compliance-label">reminder due (every {data.review_interval_months}mo)</span>
        </div>
      </div>
      {data.switches_missing_baseline.length > 0 ? (
        <p className="settings-help">
          Missing baselines: {data.switches_missing_baseline.join(', ')}. Create them on the
          Baselines page — drift detection is inactive for those switches until a baseline exists.
        </p>
      ) : null}
      {data.baselines_stale.length > 0 ? (
        <p className="settings-help">
          Reminder review due: {data.baselines_stale.join(', ')}. Refresh them on the Baselines page
          to re-attest against the current config and reset the cycle.
        </p>
      ) : null}
      <div className="row-actions">
        <button onClick={() => downloadComplianceReport('csv')}>Export CSV</button>
        <button onClick={() => downloadComplianceReport('xlsx')}>Export Excel</button>
        <button onClick={() => downloadComplianceReport('pdf')}>Export PDF</button>
      </div>
    </section>
  );
}

export function ConfigReviewPage() {
  const [filters, setFilters] = useState<ReviewFilters>({});
  const { data: reviews = [] } = useReviews(filters);
  const update = useReviewStatus();
  const [selected, setSelected] = useState<number | null>(null);
  const [diff, setDiff] = useState<string | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);

  useEffect(() => {
    if (selected === null) return;
    let cancelled = false;
    setDiff(null);
    setDiffError(null);
    fetchReviewDiff(selected)
      .then((t) => { if (!cancelled) setDiff(t); })
      .catch((err) => { if (!cancelled) setDiffError(err.message ?? 'Failed to load diff'); });
    return () => { cancelled = true; };
  }, [selected]);

  function act(reviewId: number, status: ConfigReviewStatus) {
    const comment = window.prompt(`Comment for ${status} review #${reviewId}?`, '') ?? undefined;
    update.mutate({ id: reviewId, status, comment });
  }

  return (
    <main>
      <p className="marker">/08 · REVIEW</p>
      <h1 className="headline">Config changes, reviewed.</h1>
      <p className="muted">
        Workflow: define a golden-config baseline → every backup is compared against it → any drift
        opens a review here → approve or flag it with a comment. All of it is logged as ISO 27001
        A.8.9 evidence.
      </p>

      <CompliancePanel />

      <section className="filter-bar">
        <label>
          Status
          <select
            value={filters.status ?? ''}
            onChange={(e) => setFilters({ ...filters, status: (e.target.value || undefined) as ConfigReviewStatus | undefined })}
          >
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="flagged">Flagged</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </label>
      </section>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr><th>ID</th><th>Switch</th><th>Created</th><th>Status</th><th>Summary</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {reviews.map((r) => (
              <tr key={r.id}>
                <td>#{r.id}</td>
                <td>{r.switch_name ?? `#${r.switch_id}`}</td>
                <td>{formatTzDateTime(r.created_at)}</td>
                <td><span className={`badge state-${r.status === 'flagged' ? 'fail' : r.status === 'approved' ? 'ok' : 'warn'}`}>{STATUS_LABEL[r.status] ?? r.status}</span></td>
                <td title={JSON.stringify(r.diff_summary)}>{summaryText(r.diff_summary)}</td>
                <td className="row-actions">
                  <button onClick={() => setSelected(selected === r.id ? null : r.id)}>Diff</button>
                  {r.status === 'pending' ? (
                    <>
                      <button onClick={() => act(r.id, 'approved')}>Approve</button>
                      <button onClick={() => act(r.id, 'flagged')}>Flag</button>
                      <button onClick={() => act(r.id, 'dismissed')}>Dismiss</button>
                    </>
                  ) : (
                    <span className="marker">{r.comment ? 'has comment' : ''}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {reviews.length === 0 ? <p className="viewer-empty">No reviews match the filter.</p> : null}
      </div>

      {selected !== null ? (
        <section className="viewer-box" aria-label="Review diff viewer">
          <header className="viewer-box-header">
            <span className="marker">REVIEW #{selected} · DIFF</span>
            <div className="row-actions">
              <button onClick={() => setSelected(null)}>Close</button>
            </div>
          </header>
          {diffError ? <p role="alert" className="viewer-empty">{diffError}</p> : null}
          {selected !== null && diff === null && !diffError ? <p className="viewer-empty">Loading…</p> : null}
          {diff !== null ? <pre className="viewer-pre">{diff}</pre> : null}
        </section>
      ) : null}

      {update.isError ? <div role="alert" className="settings-error">{humanizeError(update.error)}</div> : null}
    </main>
  );
}
