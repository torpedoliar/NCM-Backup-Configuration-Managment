import { useEffect, useState } from 'react';
import { useLocation } from 'wouter';
import {
  downloadComplianceReport,
  useBackups,
  useBaselines,
  useCreateBaseline,
  useDeleteBaseline,
  useNotifySettings,
  usePatchNotifySettings,
  usePrepareBaselineReview,
  useReviewInterval,
  useSwitches,
} from '../api/hooks';
import type { ConfigBaselineKind } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';
import { humanizeError } from '../lib/errors';

function addMonths(iso: string, months: number): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const target = new Date(d);
  target.setMonth(target.getMonth() + months);
  return target.toISOString().slice(0, 10);
}

export function BaselinesPage() {
  const [, setLocation] = useLocation();
  const { data: baselines = [], isLoading } = useBaselines();
  const { data: switches = [] } = useSwitches();
  const create = useCreateBaseline();
  const remove = useDeleteBaseline();
  const prepareReview = usePrepareBaselineReview();
  const reviewCycle = useReviewInterval();
  const { data: notifySettings } = useNotifySettings();
  const patchNotify = usePatchNotifySettings();

  const [cycleMonths, setCycleMonths] = useState<number>(6);
  const [emailHour, setEmailHour] = useState<number | null>(null);
  const [emailMinute, setEmailMinute] = useState<number | null>(null);
  const [cycleSuccess, setCycleSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (reviewCycle.months) {
      setCycleMonths(reviewCycle.months);
    }
  }, [reviewCycle.months]);

  useEffect(() => {
    if (notifySettings) {
      if (emailHour === null) setEmailHour(notifySettings.review_reminder_hour ?? 9);
      if (emailMinute === null) setEmailMinute(notifySettings.review_reminder_minute ?? 0);
    }
  }, [notifySettings, emailHour, emailMinute]);

  const [kind, setKind] = useState<ConfigBaselineKind>('switch');
  const [switchId, setSwitchId] = useState<number | ''>('');
  const [model, setModel] = useState('');
  const [backupId, setBackupId] = useState<number | ''>('');
  const [error, setError] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState<string | null>(null);

  const { data: backups = [] } = useBackups(switchId === '' ? undefined : Number(switchId));

  function handleReviewClick(baselineId: number) {
    setError(null);
    setReviewNote(null);
    prepareReview.mutate(baselineId, {
      onSuccess: (res) => {
        setLocation(`/config-review?id=${res.review_id}`);
      },
      onError: (err: unknown) => setError(humanizeError(err)),
    });
  }

  function handleSaveReviewCycle() {
    setCycleSuccess(null);
    setError(null);
    reviewCycle.save.mutate(cycleMonths, {
      onSuccess: () => {
        patchNotify.mutate(
          {
            review_reminder_hour: emailHour ?? 9,
            review_reminder_minute: emailMinute ?? 0,
          },
          {
            onSuccess: () => {
              setCycleSuccess('Pengaturan siklus review dan jam reminder berhasil disimpan.');
              setTimeout(() => setCycleSuccess(null), 4000);
            },
            onError: (err: unknown) => setError(humanizeError(err)),
          },
        );
      },
      onError: (err: unknown) => setError(humanizeError(err)),
    });
  }

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
        <p className="settings-help">
          Leave "Golden backup" empty to snapshot the latest successful backup — that is the recommended
          way. A baseline needs a real config as its source, otherwise drift can never be detected.
        </p>
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
            <select
              value={backupId}
              onChange={(e) => setBackupId(e.target.value ? Number(e.target.value) : '')}
              disabled={kind === 'switch' && switchId === ''}
            >
              <option value="">(latest successful backup)</option>
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

      <section className="settings-card">
        <h3>Review cycle</h3>
        <p className="settings-help">
          Seberapa sering setiap baseline harus di-review ulang (re-attestation ISO 27001 A.8.9).
          Jadwal pertama = tanggal baseline dibuat; tombol Review pada baris akan membuka sesi komparasi
          Golden Baseline vs Backup Terakhir untuk disetujui. Baseline yang jatuh tempo masuk bagian &quot;Reminder review&quot; di email pengingat.
        </p>
        <div className="settings-row" style={{ flexWrap: 'wrap', gap: '16px', alignItems: 'flex-end' }}>
          <label className="settings-field">
            <span>Interval review (bulan)</span>
            <input
              type="number"
              min={1}
              max={60}
              value={cycleMonths}
              onChange={(e) => setCycleMonths(Number(e.target.value))}
            />
          </label>
          <label className="settings-field">
            <span>Jam email reminder</span>
            <input
              type="number"
              min={0}
              max={23}
              value={emailHour ?? 9}
              onChange={(e) => setEmailHour(Number(e.target.value))}
            />
          </label>
          <label className="settings-field">
            <span>Menit</span>
            <input
              type="number"
              min={0}
              max={59}
              value={emailMinute ?? 0}
              onChange={(e) => setEmailMinute(Number(e.target.value))}
            />
          </label>
          <div>
            <button
              type="button"
              onClick={handleSaveReviewCycle}
              disabled={reviewCycle.save.isPending || patchNotify.isPending}
              className="btn-primary"
              style={{ padding: '8px 16px', fontWeight: 600 }}
            >
              {reviewCycle.save.isPending || patchNotify.isPending ? 'Menyimpan…' : 'Simpan Pengaturan Siklus'}
            </button>
          </div>
        </div>
        {cycleSuccess && <p className="settings-success" role="status" style={{ marginTop: '8px' }}>{cycleSuccess}</p>}
      </section>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Kind</th>
              <th>Target</th>
              <th>Golden backup</th>
              <th>Created</th>
              <th>Reminder review</th>
              <th>Last Reviewed By</th>
              <th>Last Review Date</th>
              <th>Status Terkini</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {baselines.map((b) => {
              const due = addMonths(b.created_at, reviewCycle.months);
              const overdue = new Date(due) < new Date();
              return (
                <tr key={b.id}>
                  <td>{b.kind === 'switch' ? 'Switch' : 'Model'}</td>
                  <td>{b.kind === 'switch' ? (b.switch_name ?? `#${b.switch_id}`) : b.model}</td>
                  <td>{b.backup_id ? `#${b.backup_id}` : '—'}</td>
                  <td>{formatTzDateTime(b.created_at)}</td>
                  <td>
                    <span className={overdue ? 'key-status revoked' : 'key-status'}>
                      {overdue ? 'REMINDER' : due}
                    </span>
                  </td>
                  <td>
                    {b.last_reviewed_by_name ? (
                      <span style={{ fontWeight: 600, color: 'var(--amber, #f59e0b)' }}>
                        {b.last_reviewed_by_name}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--muted, #94a3b8)', fontStyle: 'italic' }}>Belum direview</span>
                    )}
                  </td>
                  <td>
                    {b.last_reviewed_at ? (
                      formatTzDateTime(b.last_reviewed_at)
                    ) : (
                      <span style={{ color: 'var(--muted, #94a3b8)' }}>—</span>
                    )}
                  </td>
                  <td>
                    {b.last_review_status ? (
                      <span
                        className={`badge state-${
                          b.last_review_status === 'flagged'
                            ? 'fail'
                            : b.last_review_status === 'approved'
                            ? 'ok'
                            : 'warn'
                        }`}
                      >
                        {b.last_review_status.toUpperCase()}
                      </span>
                    ) : (
                      <span className="badge state-neutral">NO REVIEW</span>
                    )}
                  </td>
                  <td className="row-actions">
                    <button
                      onClick={() => handleReviewClick(b.id)}
                      disabled={prepareReview.isPending}
                      title="Buka sesi komparasi Golden Baseline vs Backup Terakhir di halaman Config Review"
                    >
                      {prepareReview.isPending ? 'Membuka…' : 'Review'}
                    </button>
                    <button
                      onClick={() => {
                        if (window.confirm(`Delete baseline #${b.id}?`)) remove.mutate(b.id);
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {baselines.length === 0 && !isLoading ? (
          <p className="viewer-empty">No baselines yet. Create one above.</p>
        ) : null}
        {remove.isError ? <div role="alert" className="settings-error">{humanizeError(remove.error)}</div> : null}
        {prepareReview.isError ? <div role="alert" className="settings-error">{humanizeError(prepareReview.error)}</div> : null}
        {reviewNote ? <p className="settings-success" role="status">{reviewNote}</p> : null}
      </div>

      <section className="settings-card">
        <h3>ISO 27001 A.8.9 compliance evidence</h3>
        <p className="settings-help">
          Export the per-switch configuration-management status — baseline coverage, last backup, open
          reviews — as audit evidence.
        </p>
        <div className="row-actions">
          <button onClick={() => downloadComplianceReport('csv')}>Export CSV</button>
          <button onClick={() => downloadComplianceReport('xlsx')}>Export Excel</button>
          <button onClick={() => downloadComplianceReport('pdf')}>Export PDF</button>
        </div>
      </section>
    </main>
  );
}
