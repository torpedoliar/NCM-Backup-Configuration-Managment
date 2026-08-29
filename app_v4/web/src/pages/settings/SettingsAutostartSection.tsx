import { useState } from 'react';
import { useAutostartStatus, useUpdateAutostart } from '../../api/hooks';
import type { AutostartMethod } from '../../api/types';
import { humanizeError } from '../../lib/errors';

const METHOD_LABEL: Record<AutostartMethod, string> = {
  task: 'Scheduled task',
  runkey: 'Registry Run key (logon only)',
};

export function SettingsAutostartSection() {
  const { data, isLoading } = useAutostartStatus();
  const update = useUpdateAutostart();
  const [method, setMethod] = useState<AutostartMethod>('runkey');
  const [trigger, setTrigger] = useState<'startup' | 'logon'>('startup');
  const [runLoggedOn, setRunLoggedOn] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  // The mechanism select is locked once installed; data.method may not match
  // the initial local `method` state, so remember the installed one for disables.
  const installedMethod = data?.method ?? null;

  if (isLoading || !data) return <p>Loading…</p>;

  function setEnabled(next: boolean) {
    setError(null);
    setMessage(null);
    update.mutate(
      {
        enabled: next,
        trigger,
        // When disabling, always target the mechanism that is actually
        // installed — the mechanism select is locked once installed, so the
        // local `method` state may not match it.
        method: next ? method : installedMethod ?? method,
        run_whether_logged_on: runLoggedOn,
        username: runLoggedOn ? username : undefined,
        password: runLoggedOn ? password : undefined,
      },
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

  const taskMethod = method === 'task';

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
            <dt>Mechanism</dt>
            <dd>{data.method ? METHOD_LABEL[data.method] : '—'}</dd>
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
          Auto-start registers the backend headless (<code>--serve</code>) so the backup scheduler keeps
          running without keeping the GUI open. Two mechanisms:
        </p>
        <ul className="settings-help">
          <li>
            <strong>Registry Run key</strong> (default): starts at user logon. No admin rights and no Task
            Scheduler access needed — works even where scheduled-task creation is blocked by policy.
          </li>
          <li>
            <strong>Scheduled task</strong>: starts at boot or logon, optionally <em>whether or not a user is
            logged on</em> (requires that user's username and password). Needs rights to create tasks.
          </li>
        </ul>

        <form
          className="settings-form"
          onSubmit={(e) => {
            e.preventDefault();
            setEnabled(!data.installed);
          }}
        >
          <label className="settings-field">
            <span>Mechanism</span>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as AutostartMethod)}
              disabled={data.installed}
            >
              <option value="runkey">Registry Run key (logon, no admin)</option>
              <option value="task">Scheduled task</option>
            </select>
          </label>
          {taskMethod && (
            <>
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
              <label className="settings-field">
                <span>Run whether user is logged on or not</span>
                <input
                  type="checkbox"
                  checked={runLoggedOn}
                  onChange={(e) => setRunLoggedOn(e.target.checked)}
                  disabled={data.installed}
                />
              </label>
              {runLoggedOn && (
                <>
                  <label className="settings-field">
                    <span>Username</span>
                    <input
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="DOMAIN\user"
                      disabled={data.installed}
                    />
                  </label>
                  <label className="settings-field">
                    <span>Password</span>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      disabled={data.installed}
                    />
                  </label>
                </>
              )}
            </>
          )}
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
          To verify: Run key — <code>reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "NCM v4 Backend"</code>.
          Scheduled task — <code>schtasks /Query /TN "NCM v4 Backend"</code> from an elevated prompt.
        </p>
      </article>
    </section>
  );
}
