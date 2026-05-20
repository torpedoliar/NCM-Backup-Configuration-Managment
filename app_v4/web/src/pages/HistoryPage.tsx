import { useState } from 'react';
import {
  downloadBackupUrl,
  useDeleteBackup,
  useFilteredBackups,
  useSwitches,
} from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import { BackupViewModal } from '../components/BackupViewModal';
import type { BackupFilters } from '../api/types';

export function HistoryPage() {
  const auth = useAuth();
  const isAdmin = auth.user?.role === 'admin';
  const [filters, setFilters] = useState<BackupFilters>({});
  const [viewing, setViewing] = useState<number | null>(null);
  const { data: switches = [] } = useSwitches();
  const { data: rows = [] } = useFilteredBackups(filters);
  const remove = useDeleteBackup();

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
      </section>

      <table className="data-table">
        <thead>
          <tr><th>Time</th><th>Switch</th><th>Type</th><th>State</th><th>Size</th><th>Message</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {rows.map((b) => {
            const switchName = switches.find((s) => s.id === b.switch_id)?.name ?? b.switch_id;
            return (
              <tr key={b.id}>
                <td>{new Date(b.created_at).toLocaleString()}</td>
                <td>{switchName}</td>
                <td><span className={`badge type-${b.backup_type}`}>{b.backup_type}</span></td>
                <td><span className={`badge state-${b.success ? 'ok' : 'fail'}`}>{b.success ? 'ok' : 'failed'}</span></td>
                <td>{b.size_bytes ? `${Math.round((b.size_bytes ?? 0) / 1024)} KB` : '—'}</td>
                <td title={b.message ?? ''}>{(b.message ?? '').slice(0, 60)}</td>
                <td className="row-actions">
                  <button onClick={() => setViewing(b.id)}>View</button>
                  <a href={downloadBackupUrl(b.id)} className="button">Download</a>
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

      {viewing !== null && <BackupViewModal backupId={viewing} onClose={() => setViewing(null)} />}
    </main>
  );
}
