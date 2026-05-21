import { useSystemStatus } from '../../api/hooks';

function fmtUptime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

export function SettingsServiceSection() {
  const { data: status } = useSystemStatus();
  return (
    <section>
      <h2>Service</h2>
      <dl className="settings-list">
        <div><dt>Status</dt><dd>{status?.service ?? '—'}</dd></div>
        <div><dt>Bind</dt><dd>{status ? `${status.host}:${status.port}` : '—'}</dd></div>
        <div><dt>Version</dt><dd>{status?.version ?? '—'}</dd></div>
        <div><dt>Started at</dt><dd>{status ? new Date(status.started_at).toLocaleString() : '—'}</dd></div>
        <div><dt>Uptime</dt><dd>{status ? fmtUptime(status.uptime_seconds) : '—'}</dd></div>
      </dl>
      <button title="Restart not yet implemented; close and reopen the app instead." disabled>
        Restart service
      </button>
    </section>
  );
}
