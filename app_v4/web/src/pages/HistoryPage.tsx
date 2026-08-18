import { useState } from 'react';
import {
  downloadBackup,
  downloadBackupReport,
  useDeleteBackup,
  useFilteredBackups,
  useSwitches,
} from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import { BackupViewModal } from '../components/BackupViewModal';
import type { BackupFilters } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';

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
  const [viewing, setViewing] = useState<number | null>(null);
  const { data: switches = [] } = useSwitches();
  const { data: rows = [] } = useFilteredBackups(filters);
  const remove = useDeleteBackup();

  function isoToDateInput(iso?: string): string {
    return iso ? iso.slice(0, 10) : '';
  }
  function dateInputToIsoStart(value: string): string | undefined {
    return value ? `${value}T00:00:00Z` : undefined;
  }
  function dateInputToIsoEnd(value: string): string | undefined {
    return value ? `${value}T23:59:59Z` : undefined;
  }

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
          {rows.map((b) => {
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

      {viewing !== null && <BackupViewModal backupId={viewing} onClose={() => setViewing(null)} />}
    </main>
  );
}
