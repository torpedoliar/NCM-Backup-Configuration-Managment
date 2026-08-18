import { useEffect, useState } from 'react';
import { usePatchTimeSettings, useTimeSettings } from '../../api/hooks';
import { formatTzDateTime } from '../../lib/fmt';
import { humanizeError } from '../../lib/errors';

export function SettingsTimeSection() {
  const { data } = useTimeSettings();
  const patch = usePatchTimeSettings();
  const [timezone, setTimezone] = useState('');
  const [ntp, setNtp] = useState('');
  const [ntpEnabled, setNtpEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setTimezone(data.timezone);
      setNtp(data.ntp_servers.join(', '));
      setNtpEnabled(data.ntp_enabled);
    }
  }, [data?.timezone, data?.ntp_enabled, data?.ntp_servers.join(',')]);

  if (!data) return <p>Loading…</p>;

  const dirty =
    timezone !== data.timezone ||
    ntpEnabled !== data.ntp_enabled ||
    ntp.split(',').map((s) => s.trim()).filter(Boolean).join(',') !== data.ntp_servers.join(',');

  function save() {
    setError(null);
    setSaved(false);
    const servers = ntp
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    patch.mutate(
      { timezone, ntp_servers: servers, ntp_enabled: ntpEnabled },
      {
        onSuccess: () => setSaved(true),
        onError: (err: unknown) => setError(humanizeError(err)),
      },
    );
  }

  const localNow = formatTzDateTime(data.server_now_local, data.timezone);
  const utcNow = formatTzDateTime(data.server_now_utc, 'UTC');

  return (
    <section>
      <h2>Time &amp; NTP</h2>
      <article className="settings-card">
        <h3>Server clock</h3>
        <dl className="settings-list">
          <div><dt>Local now ({data.timezone})</dt><dd>{localNow}</dd></div>
          <div><dt>UTC now</dt><dd>{utcNow}</dd></div>
        </dl>
      </article>
      <article className="settings-card">
        <h3>Timezone</h3>
        <p className="settings-help">
          Affects schedule firing time and timestamps shown in the UI. Default Asia/Jakarta (UTC+7).
        </p>
        <form
          className="settings-form"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <label className="settings-field">
            <span>Timezone</span>
            <select
              value={timezone}
              onChange={(e) => {
                setTimezone(e.target.value);
                setSaved(false);
              }}
            >
              {data.available_timezones.map((tz) => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
              {data.available_timezones.includes(timezone) ? null : (
                <option value={timezone}>{timezone}</option>
              )}
            </select>
          </label>
          <label className="settings-field">
            <span>NTP servers (comma separated)</span>
            <input
              value={ntp}
              placeholder="pool.ntp.org, time.google.com"
              onChange={(e) => {
                setNtp(e.target.value);
                setSaved(false);
              }}
            />
          </label>
          <label className="settings-field">
            <input
              type="checkbox"
              checked={ntpEnabled}
              onChange={(e) => {
                setNtpEnabled(e.target.checked);
                setSaved(false);
              }}
            />
            <span>Enable NTP sync (requires OS-level service or admin run)</span>
          </label>
          {error && <div role="alert" className="settings-error">{error}</div>}
          {saved && !dirty ? <div className="settings-success">Saved.</div> : null}
          <button type="submit" disabled={!dirty || patch.isPending}>
            {patch.isPending ? 'Saving…' : 'Save time settings'}
          </button>
        </form>
        <p className="settings-help settings-note">
          Note: this records the desired NTP configuration but does not modify Windows time service.
          Configure <code>w32tm</code> on the host if you need active sync.
        </p>
      </article>
    </section>
  );
}
