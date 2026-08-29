import { useBackups } from '../api/hooks';
import type { BackupRecord } from '../api/types';

export type DashboardRange = '24h' | '7d' | '30d' | '90d';

const DAYS_PER_RANGE: Record<DashboardRange, number> = { '24h': 1, '7d': 7, '30d': 30, '90d': 90 };

function dayKey(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function BackupChart({ range, fromTs }: { range: DashboardRange; fromTs?: string }) {
  const { data = [] } = useBackups(undefined, { from_ts: fromTs });
  const days = DAYS_PER_RANGE[range];
  const today = new Date();

  const buckets: { key: string; success: number; failed: number }[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setUTCDate(d.getUTCDate() - i);
    buckets.push({ key: dayKey(d), success: 0, failed: 0 });
  }
  const index = new Map(buckets.map((b, i) => [b.key, i]));

  for (const b of data as BackupRecord[]) {
    const k = dayKey(new Date(b.created_at));
    const i = index.get(k);
    if (i === undefined) continue;
    if (b.success) buckets[i].success += 1;
    else buckets[i].failed += 1;
  }

  const max = Math.max(1, ...buckets.map((b) => b.success + b.failed));

  return (
    <div className="backup-chart">
      {buckets.map((b) => (
        <div key={b.key} className="bar" data-day-bar data-key={b.key}>
          <div className="bar-success" style={{ height: `${(b.success / max) * 100}%` }} />
          <div className="bar-failed" style={{ height: `${(b.failed / max) * 100}%` }} />
          <span className="bar-label">{b.key.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}
