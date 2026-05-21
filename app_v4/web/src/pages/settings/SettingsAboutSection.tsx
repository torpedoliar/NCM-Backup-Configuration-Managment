import { useSystemMetrics, useSystemStatus } from '../../api/hooks';

function fmtBytes(n: number): string {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  if (n > 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}

export function SettingsAboutSection() {
  const { data: status } = useSystemStatus();
  const { data: metrics } = useSystemMetrics();
  return (
    <section>
      <h2>About</h2>
      <dl className="settings-list">
        <div><dt>Application</dt><dd>NCM v4 Ops Terminal</dd></div>
        <div><dt>Version</dt><dd>{status?.version ?? '—'}</dd></div>
        <div><dt>Switches under management</dt><dd>{metrics?.switches ?? '—'}</dd></div>
        <div><dt>Total backups</dt><dd>{metrics?.backups ?? '—'}</dd></div>
        <div><dt>Scheduled jobs</dt><dd>{metrics?.jobs ?? '—'}</dd></div>
        <div><dt>Failures (24h)</dt><dd>{metrics?.failures_24h ?? '—'}</dd></div>
        <div><dt>Database size</dt><dd>{status ? fmtBytes(status.db_size_bytes) : '—'}</dd></div>
        <div><dt>Data path</dt><dd>{status?.data_dir ?? '—'}</dd></div>
        <div><dt>Backups path</dt><dd>{status?.backups_dir ?? '—'}</dd></div>
        <div><dt>Logs path</dt><dd>{status?.logs_dir ?? '—'}</dd></div>
      </dl>
    </section>
  );
}
