import { useEffect, useState } from 'react';
import { fetchReviewDiff, useReviewStatus, useReviews } from '../api/hooks';
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
        Every drift from a baseline becomes a logged review (ISO 27001 A.8.9). Approve or flag with a
        comment — it is recorded as evidence.
      </p>

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
