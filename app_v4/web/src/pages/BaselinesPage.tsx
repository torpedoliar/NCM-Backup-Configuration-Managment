import { useState } from 'react';
import {
  useBackups,
  useBaselines,
  useCreateBaseline,
  useDeleteBaseline,
  useSwitches,
} from '../api/hooks';
import type { ConfigBaselineKind } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';
import { humanizeError } from '../lib/errors';

export function BaselinesPage() {
  const { data: baselines = [] } = useBaselines();
  const { data: switches = [] } = useSwitches();
  const create = useCreateBaseline();
  const remove = useDeleteBaseline();

  const [kind, setKind] = useState<ConfigBaselineKind>('switch');
  const [switchId, setSwitchId] = useState<number | ''>('');
  const [model, setModel] = useState('');
  const [backupId, setBackupId] = useState<number | ''>('');
  const [error, setError] = useState<string | null>(null);

  const { data: backups = [] } = useBackups(switchId === '' ? undefined : Number(switchId));

  function createBaseline() {
    setError(null);
    if (kind === 'switch' && switchId === '') {
      setError('Pick a switch.');
      return;
    }
    if (kind === 'model' && !model.trim()) {
      setError('Enter a model name.');
      return;
    }
    create.mutate(
      {
        kind,
        switch_id: kind === 'switch' ? Number(switchId) : null,
        model: kind === 'model' ? model.trim() : null,
        backup_id: backupId === '' ? null : Number(backupId),
      },
      {
        onSuccess: () => {
          setSwitchId('');
          setBackupId('');
        },
        onError: (err: unknown) => setError(humanizeError(err)),
      },
    );
  }

  return (
    <main>
      <p className="marker">/09 · BASELINES</p>
      <h1 className="headline">Golden configs define "known good".</h1>
      <p className="muted">
        A baseline is the config every later backup is compared against. Per-switch for one unit, or a
        model template applied to every switch of that model. Drift from a baseline creates a review.
      </p>

      <section className="settings-card">
        <h3>Create baseline</h3>
        <form
          className="settings-form"
          onSubmit={(e) => {
            e.preventDefault();
            createBaseline();
          }}
        >
          <label className="settings-field">
            <span>Kind</span>
            <select value={kind} onChange={(e) => setKind(e.target.value as ConfigBaselineKind)}>
              <option value="switch">Per switch</option>
              <option value="model">Model template</option>
            </select>
          </label>
          {kind === 'switch' ? (
            <label className="settings-field">
              <span>Switch</span>
              <select value={switchId} onChange={(e) => setSwitchId(e.target.value ? Number(e.target.value) : '')}>
                <option value="">Select…</option>
                {switches.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </label>
          ) : (
            <label className="settings-field">
              <span>Model</span>
              <input placeholder="e.g. AT-8000, Dell N1548P" value={model} onChange={(e) => setModel(e.target.value)} />
            </label>
          )}
          <label className="settings-field">
            <span>Golden backup</span>
            <select value={backupId} onChange={(e) => setBackupId(e.target.value ? Number(e.target.value) : '')} disabled={kind === 'switch' && switchId === ''}>
              <option value="">(latest backup)</option>
              {backups.slice(0, 20).map((b) => (
                <option key={b.id} value={b.id}>#{b.id} — {formatTzDateTime(b.created_at)}</option>
              ))}
            </select>
          </label>
          {error && <div role="alert" className="settings-error">{error}</div>}
          <button type="submit" disabled={create.isPending}>
            {create.isPending ? 'Creating…' : 'Create baseline'}
          </button>
        </form>
      </section>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr><th>Kind</th><th>Target</th><th>Golden backup</th><th>Created</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {baselines.map((b) => (
              <tr key={b.id}>
                <td>{b.kind === 'switch' ? 'Switch' : 'Model'}</td>
                <td>{b.kind === 'switch' ? (b.switch_name ?? `#${b.switch_id}`) : b.model}</td>
                <td>{b.backup_id ? `#${b.backup_id}` : '—'}</td>
                <td>{formatTzDateTime(b.created_at)}</td>
                <td className="row-actions">
                  <button
                    onClick={() => {
                      if (window.confirm(`Delete baseline #${b.id}?`)) remove.mutate(b.id);
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {baselines.length === 0 ? <p className="viewer-empty">No baselines yet. Create one above.</p> : null}
      </div>
    </main>
  );
}
