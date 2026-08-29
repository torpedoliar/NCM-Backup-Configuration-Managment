import { useState } from 'react';
import { BackupChart, type DashboardRange } from '../components/BackupChart';
import { FleetGrid } from '../components/FleetGrid';
import { KpiCell } from '../components/KpiCell';
import { LiveFeed } from '../components/LiveFeed';
import { OpsPanel } from '../components/OpsPanel';
import { useBackups, useSystemMetrics } from '../api/hooks';
import { useOptionalAuth } from '../auth/AuthProvider';
import { number } from '../lib/fmt';
import { toCsv } from '../lib/csv';
import '../styles/dashboard.css';

const RANGES: DashboardRange[] = ['24h', '7d', '30d', '90d'];

const DAYS_PER_RANGE: Record<DashboardRange, number> = { '24h': 1, '7d': 7, '30d': 30, '90d': 90 };

function dash(value: number | undefined): string {
  return value === undefined ? '—' : number(value);
}

function rangeFromTs(range: DashboardRange): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - DAYS_PER_RANGE[range]);
  return d.toISOString();
}

export function DashboardPage() {
  const { data: metrics } = useSystemMetrics();
  const [range, setRange] = useState<DashboardRange>('24h');
  const fromTs = rangeFromTs(range);
  const { data: backups = [] } = useBackups(undefined, { from_ts: fromTs });
  const auth = useOptionalAuth();

  const switches = metrics?.switches;
  const backupsCount = metrics?.backups;
  const failures24h = metrics?.failures_24h ?? 0;
  const failuresTotal = metrics?.failures_total ?? 0;

  function exportCsv() {
    const rows = backups.map((b) => ({
      id: b.id,
      switch_id: b.switch_id,
      taken_at: b.created_at,
      success: b.success ? 'true' : 'false',
      backup_type: b.backup_type,
      size_bytes: b.size_bytes ?? 0,
      message: b.message ?? '',
    }));
    const csv = toCsv(['id', 'switch_id', 'taken_at', 'success', 'backup_type', 'size_bytes', 'message'], rows);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backups-${range}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="dashboard-page">
      <section className="dashboard-hero">
        <div>
          <div className="marker marker-amber">OPERATIONS OVERVIEW</div>
          <h1 className="headline hero-headline">
            {dash(switches)} switches, <em>{dash(backupsCount)}</em> backups, {failures24h === 0 ? 'no' : failures24h} anomal{failures24h === 1 ? 'y' : 'ies'} in the last 24h.
          </h1>
          <div className="hero-underline" />
        </div>
        <div className="hero-meta">
          <span className="marker">/REF DSH-001</span>
          <span className="marker marker-amber">LIVE</span>
        </div>
      </section>

      <section className="range-tabs" aria-label="time range">
        {RANGES.map((r) => (
          <button
            key={r}
            data-active={r === range}
            className={r === range ? 'active' : ''}
            onClick={() => setRange(r)}
          >
            {r.toUpperCase()}
          </button>
        ))}
        <button onClick={exportCsv}>EXPORT ↗</button>
      </section>

      <section className="kpi-grid">
        <KpiCell marker="/01 · INV" label="SWITCHES UNDER MGMT" value={dash(switches)} />
        <KpiCell marker="/02 · EXEC" label="BACKUPS" value={dash(backupsCount)} />
        <KpiCell
          marker="/03 · QOS"
          label="SUCCESS RATE"
          value={
            backupsCount && backupsCount > 0
              ? (((backupsCount - failuresTotal) / backupsCount) * 100).toFixed(1)
              : '—'
          }
          suffix="%"
        />
        <KpiCell
          marker="/04 · ALERT"
          label="FAILED · 24H"
          value={String(failures24h).padStart(2, '0')}
          tone={failures24h > 0 ? 'red' : undefined}
        />
      </section>

      <section className="dashboard-grid">
        <OpsPanel marker="/05 · TIMESERIES" title={`Backup activity, last ${range}`} className="chart-panel">
          <BackupChart range={range} fromTs={fromTs} />
        </OpsPanel>
        <OpsPanel marker="/06 · STREAM" title="Live activity" className="live-panel">
          <LiveFeed />
        </OpsPanel>
      </section>

      <OpsPanel marker="/07 · FLEET" title="Switch fleet, at a glance" className="fleet-panel">
        <FleetGrid />
      </OpsPanel>
    </main>
  );
}
