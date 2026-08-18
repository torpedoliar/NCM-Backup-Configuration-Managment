import { useLiveEvents } from '../store/live-events';
import type { LiveEvent } from '../api/types';

function activeBackups(events: LiveEvent[]): { switch_id: number; name: string }[] {
  const last = new Map<number, { state: string; ts: number; name: string }>();
  for (const event of events) {
    const id = event.payload.switch_id;
    if (typeof id !== 'number') continue;
    const ts = Date.parse(event.ts);
    const prev = last.get(id);
    if (!prev || ts > prev.ts) {
      last.set(id, { state: event.type, ts, name: String(event.payload.switch_name ?? '') });
    }
  }
  return [...last.entries()]
    .filter(([, s]) => s.state === 'backup_started')
    .map(([id, s]) => ({ switch_id: id, name: s.name }));
}

export function BackupProgress() {
  const events = useLiveEvents((s) => s.events);
  const running = activeBackups(events);
  if (running.length === 0) return null;
  const label =
    running.length > 3 ? `${running.length} backups running` : `Backup ${running.map((r) => r.name || `#${r.switch_id}`).join(', ')}`;
  return (
    <span className="backup-progress" role="status">
      <span className="backup-progress-bar" />
      {label}
    </span>
  );
}