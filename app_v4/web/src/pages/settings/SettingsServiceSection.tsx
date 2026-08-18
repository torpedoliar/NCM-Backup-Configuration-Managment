import { useEffect, useState } from 'react';
import { useBackupLocation, usePatchBackupLocation, useSystemStatus } from '../../api/hooks';
import { formatTzDateTime } from '../../lib/fmt';
import { humanizeError } from '../../lib/errors';

function fmtUptime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

export function SettingsServiceSection() {
  const { data: status } = useSystemStatus();
  const { data: backupLocation } = useBackupLocation();
  const patchBackupLocation = usePatchBackupLocation();
  const [backupRoot, setBackupRoot] = useState('');
  const [backupError, setBackupError] = useState<string | null>(null);
  const [backupSaved, setBackupSaved] = useState(false);

  useEffect(() => {
    if (backupLocation) setBackupRoot(backupLocation.backup_root_folder);
  }, [backupLocation?.backup_root_folder]);

  function saveBackupLocation() {
    setBackupError(null);
    setBackupSaved(false);
    patchBackupLocation.mutate(
      { backup_root_folder: backupRoot.trim() },
      {
        onSuccess: () => setBackupSaved(true),
        onError: (err: unknown) => setBackupError(humanizeError(err)),
      },
    );
  }

  const dirty = backupLocation ? backupRoot.trim() !== backupLocation.backup_root_folder : false;
  const empty = backupRoot.trim() === '';

  return (
    <section>
      <h2>Service</h2>
      <dl className="settings-list">
        <div><dt>Status</dt><dd>{status?.service ?? '—'}</dd></div>
        <div><dt>Bind</dt><dd>{status ? `${status.host}:${status.port}` : '—'}</dd></div>
        <div><dt>Version</dt><dd>{status?.version ?? '—'}</dd></div>
        <div><dt>Started at</dt><dd>{status ? formatTzDateTime(status.started_at) : '—'}</dd></div>
        <div><dt>Uptime</dt><dd>{status ? fmtUptime(status.uptime_seconds) : '—'}</dd></div>
      </dl>
      <button title="Restart not yet implemented; close and reopen the app instead." disabled>
        Restart service
      </button>

      <article className="settings-card">
        <h3>Backup Location</h3>
        <p className="settings-help">
          Folder where new backup files are written. Absolute paths
          (e.g. <code>D:/NCM/backups</code>) are stored as-is. Relative paths resolve under the
          application data directory.
        </p>
        <p>
          <strong>Resolved path:</strong>{' '}
          <code>{backupLocation?.resolved_backups_dir ?? '—'}</code>
        </p>
        <form
          className="settings-form"
          onSubmit={(event) => {
            event.preventDefault();
            saveBackupLocation();
          }}
        >
          <label className="settings-field">
            <span>Backup root folder</span>
            <input
              value={backupRoot}
              placeholder="e.g. D:/NCM/backups or backups"
              onChange={(event) => {
                setBackupRoot(event.target.value);
                setBackupSaved(false);
              }}
            />
          </label>
          {backupError && <div role="alert" className="settings-error">{backupError}</div>}
          {backupSaved && !dirty ? (
            <div className="settings-success">Saved. New backups will use this location.</div>
          ) : null}
          <button
            type="submit"
            disabled={empty || !dirty || patchBackupLocation.isPending}
          >
            {patchBackupLocation.isPending ? 'Saving…' : 'Save backup location'}
          </button>
        </form>
        <p className="settings-help settings-note">
          Existing backup files stay where they are. Move them manually if you want history under
          the new path.
        </p>
      </article>
    </section>
  );
}
