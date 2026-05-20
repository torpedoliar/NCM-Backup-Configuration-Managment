import { BackupChart } from '../components/BackupChart';
import { FleetGrid } from '../components/FleetGrid';
import { KpiCell } from '../components/KpiCell';
import { LiveFeed } from '../components/LiveFeed';
import { useSystemMetrics } from '../api/hooks';
import { useOptionalAuth } from '../auth/AuthProvider';
import { useLiveSocket } from '../lib/ws';
import { number } from '../lib/fmt';

export function DashboardPage() {
  const { data } = useSystemMetrics();
  const auth = useOptionalAuth();
  useLiveSocket(auth?.accessToken ?? null);
  return (
    <main>
      <h1 className="headline">Twelve switches, <span>three-forty-eight</span> backups, one anomaly.</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <KpiCell marker="/01 · INV" label="Switches" value={number(data?.switches ?? 12)} />
        <KpiCell marker="/02 · BAK" label="Backups" value={number(data?.backups ?? 348)} />
        <KpiCell marker="/03 · SCH" label="Jobs" value={number(data?.jobs ?? 9)} />
        <KpiCell marker="/04 · ERR" label="24h failures" value={number(data?.failures_24h ?? 1)} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginTop: 16 }}>
        <section style={{ border: '1px solid var(--line)', padding: 16 }}><BackupChart /></section>
        <LiveFeed />
      </div>
      <div style={{ marginTop: 16 }}><FleetGrid /></div>
    </main>
  );
}
