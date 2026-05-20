import { useState } from 'react';
import { useAudit } from '../api/hooks';
import type { AuditFilters } from '../api/types';

const ACTION_GROUPS: Record<string, string> = {
  All: '',
  Auth: 'auth.',
  Switch: 'switch.',
  Credential: 'credential.',
  Schedule: 'schedule.',
  User: 'user.',
  Backup: 'backup.',
  System: 'system.',
};

const PAGE_STEP = 50;

export function AuditPage() {
  const [filters, setFilters] = useState<AuditFilters>({ limit: PAGE_STEP, offset: 0 });
  const [expanded, setExpanded] = useState<number | null>(null);
  const { data } = useAudit(filters);
  const rows = data?.rows ?? [];
  const total = data?.total ?? 0;

  return (
    <main>
      <p className="marker">/AUDIT</p>
      <h1 className="headline">Activity ledger.</h1>

      <section className="filter-bar">
        <label>
          Action
          <select
            onChange={(event) =>
              setFilters({ ...filters, action: event.target.value || undefined, offset: 0 })
            }
          >
            {Object.entries(ACTION_GROUPS).map(([label, prefix]) => (
              <option key={label} value={prefix}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </section>

      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>User</th>
            <th>Action</th>
            <th>Target</th>
            <th>IP</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.ts).toLocaleString()}</td>
              <td>{row.user_id ?? 'system'}</td>
              <td>
                <span className={`badge action-${row.action.split('.')[0]}`}>{row.action}</span>
              </td>
              <td>{row.target_type ? `${row.target_type}:${row.target_id}` : '—'}</td>
              <td>{row.ip ?? '—'}</td>
              <td>
                {row.detail_json ? (
                  <button
                    type="button"
                    onClick={() => setExpanded(expanded === row.id ? null : row.id)}
                  >
                    {expanded === row.id ? 'Hide' : 'View JSON'}
                  </button>
                ) : (
                  '—'
                )}
                {expanded === row.id && row.detail_json ? (
                  <pre className="audit-detail">{JSON.stringify(row.detail_json, null, 2)}</pre>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <footer className="audit-footer">
        <span>
          {rows.length} of {total}
        </span>
        {rows.length < total ? (
          <button
            type="button"
            onClick={() =>
              setFilters({ ...filters, limit: (filters.limit ?? PAGE_STEP) + PAGE_STEP })
            }
          >
            Load {PAGE_STEP} more
          </button>
        ) : null}
      </footer>
    </main>
  );
}
