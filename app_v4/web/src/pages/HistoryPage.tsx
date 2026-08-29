import { useEffect, useState } from 'react';
import {
  downloadBackup,
  downloadBackupReport,
  fetchBackupContent,
  useDeleteBackup,
  usePagedBackups,
  useSwitches,
} from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import type { BackupFilters } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';

const BACKUPS_PER_PAGE = 10;

function defaultFromIso(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
}

export function HistoryPage() {
  const auth = useAuth();
  const isAdmin = auth.user?.role === 'admin';
  const [filters, setFilters] = useState<BackupFilters>(() => ({
    from_ts: `${defaultFromIso()}T00:00:00Z`,
  }));
  const [page, setPage] = useState(0);
  const [viewing, setViewing] = useState<number | null>(null);
  const [viewText, setViewText] = useState<string | null>(null);
  const [viewError, setViewError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: switches = [] } = useSwitches();
  const paged = usePagedBackups(filters, { offset: page * BACKUPS_PER_PAGE, limit: BACKUPS_PER_PAGE });
  const rows = paged.data?.rows ?? [];
  const total = paged.data?.total ?? 0;
  const remove = useDeleteBackup();

  useEffect(() => {
    setPage(0);
  }, [filters]);

  useEffect(() => {
    if (viewing === null) return;
    let cancelled = false;
    setViewText(null);
    setViewError(null);
    fetchBackupContent(viewing)
      .then((t) => { if (!cancelled) setViewText(t); })
      .catch((err) => { if (!cancelled) setViewError(err.message ?? 'Failed to load'); });
    return () => { cancelled = true; };
  }, [viewing]);

  const pageCount = Math.max(1, Math.ceil(total / BACKUPS_PER_PAGE));
  const safePage = Math.min(page, pageCount - 1);

  function isoToDateInput(iso?: string): string {
    return iso ? iso.slice(0, 10) : '';
  }
  function dateInputToIsoStart(value: string): string | undefined {
    return value ? `${value}T00:00:00Z` : undefined;
  }
  function dateInputToIsoEnd(value: string): string | undefined {
    return value ? `${value}T23:59:59Z` : undefined;
  }

  async function copy() {
    if (viewText === null) return;
    try {
      await navigator.clipboard.writeText(viewText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API may be unavailable; ignore silently.
    }
  }

  const pageRows = rows;

  return (
    <main>
      <p className="marker">/05 · HIST</p>
      <h1 className="headline">Every config has a trail.</h1>

      <section className="filter-bar">
        <label>
          Switch
          <select
            value={filters.switch_id ?? ''}
            onChange={(event) => setFilters({ ...filters, switch_id: event.target.value ? Number(event.target.value) : undefined })}
          >
            <option value="">All</option>
            {switches.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>
        <label>
          Type
          <select
            value={filters.backup_type ?? ''}
            onChange={(event) => setFilters({ ...filters, backup_type: (event.target.value || undefined) as BackupFilters['backup_type'] })}
          >
            <option value="">All</option>
            <option value="manual">Manual</option>
            <option value="automatic">Automatic</option>
            <option value="manual_schedule">Manual (schedule)</option>
          </select>
        </label>
        <label>
          State
          <select
            value={filters.success === undefined ? '' : filters.success ? 'success' : 'failed'}
            onChange={(event) => {
              const v = event.target.value;
              setFilters({ ...filters, success: v === '' ? undefined : v === 'success' });
            }}
          >
            <option value="">All</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
          </select>
        </label>
        <label>
          Search
          <input
            value={filters.q ?? ''}
            onChange={(event) => setFilters({ ...filters, q: event.target.value || undefined })}
          />
        </label>
        <label>
          From
          <input
            type="date"
            value={isoToDateInput(filters.from_ts)}
            onChange={(event) => setFilters({ ...filters, from_ts: dateInputToIsoStart(event.target.value) })}
          />
        </label>
        <label>
          To
          <input
            type="date"
            value={isoToDateInput(filters.to_ts)}
            onChange={(event) => setFilters({ ...filters, to_ts: dateInputToIsoEnd(event.target.value) })}
          />
        </label>
      </section>

      <div className="action-row" style={{ margin: '12px 0' }}>
        <span className="marker">EXPORT</span>
        <button onClick={() => downloadBackupReport('csv', filters)}>Export CSV</button>
        <button onClick={() => downloadBackupReport('xlsx', filters)}>Export Excel</button>
        <button onClick={() => downloadBackupReport('pdf', filters)}>Export PDF</button>
      </div>

      <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr><th>Time</th><th>Switch</th><th>Type</th><th>State</th><th>Size</th><th>Message</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {pageRows.map((b) => {
            const switchName = switches.find((s) => s.id === b.switch_id)?.name ?? b.switch_id;
            return (
              <tr key={b.id}>
                <td>{formatTzDateTime(b.created_at)}</td>
                <td>{switchName}</td>
                <td><span className={`badge type-${b.backup_type}`}>{b.backup_type}</span></td>
                <td><span className={`badge state-${b.success ? 'ok' : 'fail'}`}>{b.success ? 'ok' : 'failed'}</span></td>
                <td>{b.size_bytes ? `${Math.round((b.size_bytes ?? 0) / 1024)} KB` : '—'}</td>
                <td title={b.message ?? ''}>{(b.message ?? '').slice(0, 60)}</td>
                <td className="row-actions">
                  <button onClick={() => setViewing(b.id)}>View</button>
                  <button onClick={() => downloadBackup(b.id)}>Download</button>
                  {isAdmin && (
                    <button onClick={() => {
                      if (window.confirm(`Delete backup #${b.id}? Backup file will be removed.`)) {
                        remove.mutate(b.id);
                      }
                    }}>Delete</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>

      <div className="pager">
        <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={safePage === 0}>‹ Prev</button>
        <span className="marker">PAGE {safePage + 1} / {pageCount}</span>
        <button onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))} disabled={safePage >= pageCount - 1}>Next ›</button>
      </div>

      <section className="viewer-box" aria-label="Backup config viewer">
        <header className="viewer-box-header">
          <span className="marker">VIEW CONFIG{viewing !== null ? ` · BACKUP #${viewing}` : ''}</span>
          {viewing !== null && (
            <div className="row-actions">
              <button onClick={copy} disabled={viewText === null}>
                {copied ? 'Copied!' : 'Copy'}
              </button>
              <button onClick={() => setViewing(null)}>Close</button>
            </div>
          )}
        </header>
        {viewError ? <p role="alert" className="viewer-empty">{viewError}</p> : null}
        {viewing !== null && viewText === null && !viewError ? <p className="viewer-empty">Loading…</p> : null}
        {viewText !== null ? <pre className="viewer-pre">{viewText}</pre> : null}
        {viewing === null ? (
          <p className="viewer-empty">Select a backup and click View to inspect its config here.</p>
        ) : null}
      </section>
    </main>
  );
}
