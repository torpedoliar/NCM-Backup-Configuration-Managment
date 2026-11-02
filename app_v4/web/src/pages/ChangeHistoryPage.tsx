import { useEffect, useState } from 'react';
import { fetchReviewDiff, useReviews } from '../api/hooks';
import type { ConfigReview, ReviewFilters } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';

/** One-line summary of a drift record's structured diff. */
function summaryText(summary: Record<string, unknown>): string {
  const parts: string[] = [];
  const nums = (value: unknown): number[] => (Array.isArray(value) ? (value as number[]) : []);
  const strs = (value: unknown): string[] => (Array.isArray(value) ? (value as string[]) : []);

  const added = nums(summary.vlans_added);
  const removed = nums(summary.vlans_removed);
  const renamed = nums(summary.vlans_renamed);
  const changed = strs(summary.ports_changed);

  if (added.length) parts.push(`VLAN +${added.join(',')}`);
  if (removed.length) parts.push(`VLAN -${removed.join(',')}`);
  if (renamed.length) parts.push(`VLAN renamed ${renamed.join(',')}`);
  if (changed.length) parts.push(`${changed.length} port(s) changed (${changed.slice(0, 5).join(', ')})`);
  if (summary.hostname_changed) parts.push('hostname changed');
  return parts.join(' · ') || 'text diff only';
}

/**
 * Change History (Riwayat Perubahan).
 *
 * The automatic record of every configuration change detected when a backup is
 * compared with its golden baseline (origin "drift"). Read-only evidence — the
 * periodic ISO 27001 A.8.9 attestation tickets stay on Config Review.
 */
export function ChangeHistoryPage() {
  const [filters] = useState<ReviewFilters>({ origin: 'drift' });
  const { data: reviews = [], isLoading } = useReviews(filters);
  const [query, setQuery] = useState('');
  const [viewing, setViewing] = useState<number | null>(null);
  const [diffText, setDiffText] = useState<string | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);

  useEffect(() => {
    if (viewing === null) return;
    let cancelled = false;
    setDiffText(null);
    setDiffError(null);
    fetchReviewDiff(viewing)
      .then((text) => { if (!cancelled) setDiffText(text); })
      .catch((err) => { if (!cancelled) setDiffError(err?.message ?? 'Failed to load diff'); });
    return () => { cancelled = true; };
  }, [viewing]);

  const needle = query.trim().toLowerCase();
  const rows: ConfigReview[] = needle
    ? reviews.filter((row) =>
        [String(row.id), row.switch_name ?? '', summaryText(row.diff_summary)]
          .join(' ')
          .toLowerCase()
          .includes(needle),
      )
    : reviews;

  return (
    <main>
      <p className="marker">/CHG · HISTORY</p>
      <h1 className="headline">Every change leaves evidence.</h1>

      <section className="filter-bar">
        <label>
          Search
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Switch, ID, or change…"
          />
        </label>
      </section>

      <div className="action-row" style={{ margin: '12px 0' }}>
        <span className="marker">
          SHOWING {rows.length} OF {reviews.length} CHANGE RECORDS
        </span>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Detected</th>
              <th>Switch</th>
              <th>Change summary</th>
              <th>State</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="marker">
                  {isLoading ? 'Loading…' : 'No configuration changes recorded yet.'}
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="marker">#{row.id}</td>
                <td>{formatTzDateTime(row.created_at)}</td>
                <td>{row.switch_name ?? `#${row.switch_id}`}</td>
                <td title={JSON.stringify(row.diff_summary)}>{summaryText(row.diff_summary)}</td>
                <td><span className="badge state-warn">{row.status}</span></td>
                <td className="row-actions">
                  <button onClick={() => setViewing(row.id)}>View diff</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="viewer-box" aria-label="Change diff viewer">
        <header className="viewer-box-header">
          <span className="marker">
            VIEW DIFF{viewing !== null ? ` · REVIEW #${viewing}` : ''}
          </span>
          {viewing !== null && (
            <div className="row-actions">
              <button onClick={() => setViewing(null)}>Close</button>
            </div>
          )}
        </header>
        {diffError ? <p role="alert" className="viewer-empty">{diffError}</p> : null}
        {viewing !== null && diffText === null && !diffError ? <p className="viewer-empty">Loading…</p> : null}
        {diffText !== null ? <pre className="viewer-pre">{diffText}</pre> : null}
        {viewing === null ? (
          <p className="viewer-empty">Select a change record and click View diff to inspect it here.</p>
        ) : null}
      </section>
    </main>
  );
}
