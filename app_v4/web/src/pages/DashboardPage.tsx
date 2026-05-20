import { BackupChart } from '../components/BackupChart';
import { FleetGrid } from '../components/FleetGrid';
import { KpiCell } from '../components/KpiCell';
import { LiveFeed } from '../components/LiveFeed';
import { OpsPanel } from '../components/OpsPanel';
import { useSystemMetrics } from '../api/hooks';
import { useOptionalAuth } from '../auth/AuthProvider';
import { useLiveSocket } from '../lib/ws';
import { number } from '../lib/fmt';
import '../styles/dashboard.css';

export function DashboardPage() {
  const { data } = useSystemMetrics();
  const auth = useOptionalAuth();
  useLiveSocket(auth?.accessToken ?? null);

  const switches = data?.switches ?? 12;
  const backups = data?.backups ?? 348;
  const failures = data?.failures_24h ?? 1;

  return (
    <main className="dashboard-page">
      <section className="dashboard-hero">
        <div>
          <div className="marker marker-amber">OPERATIONS OVERVIEW</div>
          <h1 className="headline hero-headline">
            Twelve switches, <em>three-forty-eight</em>
            <br />
            backups, one anomaly.
          </h1>
          <p className="hero-subline marker">// LAST 30 DAYS · AUTO-REFRESH 30s · DATA-AS-OF 22:00:22</p>
          <div className="hero-underline" />
        </div>
        <div className="hero-meta">
          <span className="marker">/REF DSH-001</span>
          <span className="marker marker-amber">LIVE</span>
        </div>
      </section>

      <section className="range-tabs" aria-label="time range">
        <button className="active">24H</button>
        <button>7D</button>
        <button>30D</button>
        <button>90D</button>
        <button>EXPORT ↗</button>
      </section>

      <section className="kpi-grid">
        <KpiCell
          marker="/01 · INV"
          label="SWITCHES UNDER MGMT"
          value={number(switches)}
          delta="+2 NEW"
          tone="green"
        />
        <KpiCell
          marker="/02 · EXEC"
          label="BACKUPS · 30D"
          value={number(backups)}
          delta="↑ 12.4%"
          tone="green"
        />
        <KpiCell
          marker="/03 · QOS"
          label="SUCCESS RATE"
          value="96.3"
          suffix="%"
          footer="TARGET 99.0% · DELTA -2.7"
          progress={96}
        />
        <KpiCell
          marker="/04 · ALERT"
          label="FAILED · 24H"
          value={String(failures).padStart(2, '0')}
          delta="△ TIMEOUT"
          tone="red"
          footer="SW-EDGE-07 · 10.0.1.7"
        />
      </section>

      <section className="dashboard-grid">
        <OpsPanel marker="/05 · TIMESERIES" title="Backup activity, last fourteen days" className="chart-panel">
          <BackupChart />
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
