import { useState } from 'react';
import { useAutostartStatus, useUpdateAutostart } from '../../api/hooks';
import { humanizeError } from '../../lib/errors';

export function SettingsAutostartSection() {
  const { data, isLoading } = useAutostartStatus();
  const update = useUpdateAutostart();
  const [trigger, setTrigger] = useState<'startup' | 'logon'>('startup');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  if (isLoading || !data) return <p>Loading…</p>;

  function setEnabled(next: boolean) {
    setError(null);
    setMessage(null);
    update.mutate(
      { enabled: next, trigger },
      {
        onSuccess: (status) =>
          setMessage(
            next
              ? `Auto-start enabled (${status.raw_status ?? 'Ready'}).`
              : 'Auto-start disabled.',
          ),
        onError: (err: unknown) => setError(humanizeError(err)),
      },
    );
  }

  return (
    <section>
      <h2>Auto-start (Windows)</h2>
      <article className="settings-card">
        <h3>Status</h3>
        <dl className="settings-list">
          <div>
            <dt>State</dt>
            <dd>
              {data.installed
                ? data.ready
                  ? `Installed · ${data.raw_status ?? 'Ready'}`
                  : `Installed · ${data.raw_status ?? 'Disabled'}`
                : 'Not installed'}
            </dd>
          </div>
          <div>
            <dt>Executable</dt>
            <dd>
              <code>{data.executable_path ?? '— (running from source; auto-start not supported)'}</code>
            </dd>
          </div>
        </dl>
      </article>

      <article className="settings-card">
        <h3>Configure</h3>
        <p className="settings-help">
          Enable auto-start to register a Windows scheduled task that launches the backend
          headless (<code>--serve</code>) at boot or logon. The backup scheduler then keeps running
          across reboots without keeping the GUI open.
        </p>
        <p className="settings-help">
          Requires admin privileges on the host. The task runs with <strong>HIGHEST</strong>{' '}
          privileges so the backend can bind its port and access DPAPI-protected secrets.
        </p>

        <form
          className="settings-form"
          onSubmit={(e) => {
            e.preventDefault();
            setEnabled(!data.installed);
          }}
        >
          <label className="settings-field">
            <span>Trigger</span>
            <select
              value={trigger}
              onChange={(e) => setTrigger(e.target.value as 'startup' | 'logon')}
              disabled={data.installed}
            >
              <option value="startup">At system startup (recommended)</option>
              <option value="logon">At user logon</option>
            </select>
          </label>
          {error && <div role="alert" className="settings-error">{error}</div>}
          {message && <div className="settings-success">{message}</div>}
          <div className="action-row">
            <button
              type="button"
              onClick={() => setEnabled(true)}
              disabled={update.isPending || (data.installed && data.ready)}
            >
              {update.isPending && !data.installed ? 'Enabling…' : 'Enable auto-start'}
            </button>
            <button
              type="button"
              onClick={() => setEnabled(false)}
              disabled={update.isPending || !data.installed}
            >
              {update.isPending && data.installed ? 'Disabling…' : 'Disable auto-start'}
            </button>
          </div>
        </form>

        <p className="settings-help settings-note">
          To verify, open Task Scheduler and look for "NCM v4 Backend". You can also run{' '}
          <code>schtasks /Query /TN "NCM v4 Backend"</code> from an elevated prompt.
        </p>
      </article>
    </section>
  );
}
