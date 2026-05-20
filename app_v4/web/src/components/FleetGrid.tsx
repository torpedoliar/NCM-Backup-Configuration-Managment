import { useLatestBackupPerSwitch, useSwitches } from '../api/hooks';
import type { BackupRecord, SwitchRecord } from '../api/types';

type State = 'ok' | 'warn' | 'fail' | 'unknown';

const WARN_AFTER_MS = 24 * 60 * 60 * 1000;

function deriveState(latest: BackupRecord | undefined): State {
  if (!latest) return 'unknown';
  if (!latest.success) return 'fail';
  const age = Date.now() - Date.parse(latest.created_at);
  return age > WARN_AFTER_MS ? 'warn' : 'ok';
}

function ageLabel(latest: BackupRecord | undefined): string {
  if (!latest) return '—';
  const ms = Date.now() - Date.parse(latest.created_at);
  if (Number.isNaN(ms)) return '—';
  const minutes = Math.floor(ms / 60000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

export function FleetGrid() {
  const { data: switches = [] } = useSwitches();
  const { data: backups = [] } = useLatestBackupPerSwitch();

  const latestBySwitch = new Map<number, BackupRecord>();
  for (const backup of backups) {
    const existing = latestBySwitch.get(backup.switch_id);
    if (!existing || Date.parse(backup.created_at) > Date.parse(existing.created_at)) {
      latestBySwitch.set(backup.switch_id, backup);
    }
  }

  if (switches.length === 0) {
    return <p className="muted">No switches under management yet.</p>;
  }

  return (
    <ul role="list" className="fleet-grid">
      {switches.map((sw: SwitchRecord) => {
        const latest = latestBySwitch.get(sw.id);
        const state = deriveState(latest);
        return (
          <li key={sw.id} role="listitem" data-state={state} title={`${sw.ip} · ${sw.protocol}`}>
            <span className="fleet-name">{sw.name}</span>
            <span className={`fleet-state state-${state}`}>{state.toUpperCase()}</span>
            <span className="fleet-age">{ageLabel(latest)}</span>
          </li>
        );
      })}
    </ul>
  );
}
