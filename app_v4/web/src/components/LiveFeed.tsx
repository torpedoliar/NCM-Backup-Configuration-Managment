import { Link } from 'wouter';
import { useLiveEvents } from '../store/live-events';
import { useOptionalAuth } from '../auth/AuthProvider';
import { formatTzTime } from '../lib/fmt';

function describe(event: { type: string; payload: Record<string, unknown> }): string {
  const name = (event.payload.switch_name as string | undefined) ?? '';
  switch (event.type) {
    case 'backup_completed':
      return `${name} backup completed`.trim();
    case 'backup_failed':
      return `${name} backup failed${event.payload.message ? `: ${event.payload.message}` : ''}`.trim();
    case 'backup_started':
      return `${name} backup started`.trim();
    case 'job_triggered':
      return `Scheduled job triggered (switch ${event.payload.switch_id ?? '?'})`;
    case 'config_drift':
      return `${name} config drift detected, review #${event.payload.review_id ?? '?'}`.trim();
    default:
      return event.type;
  }
}

function fmtTime(iso: string): string {
  return formatTzTime(iso);
}

export function LiveFeed() {
  const events = useLiveEvents((s) => s.events);
  const count = useLiveEvents((s) => s.countLast24h());
  const auth = useOptionalAuth();
  const isAdmin = auth?.user?.role === 'admin';

  if (events.length === 0) {
    return <p className="muted">No recent activity yet.</p>;
  }

  return (
    <div className="live-feed">
      <ul role="list">
        {events.map((event, idx) => (
          <li key={`${event.ts}-${idx}`}>
            <span className="ts">{fmtTime(event.ts)}</span>
            <span className={`evt evt-${event.type}`}>{describe(event)}</span>
          </li>
        ))}
      </ul>
      <footer className="live-feed-footer">
        <span><b>{count}</b> EVENTS / 24H</span>
        {isAdmin ? <Link href="/audit" className="view-all">VIEW ALL ↗</Link> : null}
      </footer>
    </div>
  );
}
