import { useEffect, useState } from 'react';
import { useNotifySettings, usePatchNotifySettings, useTestNotify } from '../../api/hooks';
import type { NotifySettings } from '../../api/types';
import { humanizeError } from '../../lib/errors';

export function SettingsNotificationsSection() {
  const { data } = useNotifySettings();
  const patch = usePatchNotifySettings();
  const test = useTestNotify();
  const [draft, setDraft] = useState<NotifySettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  useEffect(() => {
    if (data) setDraft({ ...data, email_to: [...data.email_to] });
  }, [data]);

  if (!draft || !data) return <p>Loading…</p>;

  const dirtyKeys = (Object.keys(draft) as (keyof NotifySettings)[]).filter(
    (key) => JSON.stringify(draft![key]) !== JSON.stringify(data[key]),
  );

  function save() {
    setError(null);
    if (!data || !draft) return;
    const d = draft;
    const updates: Partial<NotifySettings> = {};
    for (const key of dirtyKeys) {
      (updates as Record<string, unknown>)[key] = d[key];
    }
    if (updates.email_to !== undefined) {
      updates.email_to = d.email_to.map((e) => e.trim()).filter(Boolean);
    }
    patch.mutate(updates, { onError: (err: unknown) => setError(humanizeError(err)) });
  }

  function testNow() {
    setTestError(null);
    setTestResult(null);
    test.mutate(undefined, {
      onSuccess: (r) => setTestResult(`Test email sent (${r.channel}).`),
      onError: (err: unknown) => setTestError(humanizeError(err)),
    });
  }

  function setStr(key: 'webhook_url' | 'telegram_token' | 'telegram_chat_id' | 'smtp_host' | 'smtp_username' | 'smtp_password' | 'app_public_url', value: string) {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  return (
    <section>
      <h2>Notifications</h2>
      <form
        className="settings-form"
        onSubmit={(event) => {
          event.preventDefault();
          save();
        }}
      >
        <label className="settings-field settings-checkbox">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
          />
          <span>Enable notifications</span>
        </label>
        <label className="settings-field">
          <span>Webhook URL</span>
          <input
            type="text"
            placeholder="https://hooks.example.com/…"
            value={draft.webhook_url}
            onChange={(e) => setStr('webhook_url', e.target.value)}
          />
        </label>

        <h3>Telegram (drift alerts)</h3>
        <label className="settings-field">
          <span>Bot token</span>
          <input type="password" value={draft.telegram_token} onChange={(e) => setStr('telegram_token', e.target.value)} />
        </label>
        <label className="settings-field">
          <span>Chat ID</span>
          <input type="text" value={draft.telegram_chat_id} onChange={(e) => setStr('telegram_chat_id', e.target.value)} />
        </label>

        <h3>Email (review reminders)</h3>
        <label className="settings-field settings-checkbox">
          <input
            type="checkbox"
            checked={draft.email_enabled}
            onChange={(e) => setDraft({ ...draft, email_enabled: e.target.checked })}
          />
          <span>Enable email reminders</span>
        </label>
        <label className="settings-field">
          <span>SMTP host</span>
          <input type="text" value={draft.smtp_host} onChange={(e) => setStr('smtp_host', e.target.value)} />
        </label>
        <label className="settings-field">
          <span>SMTP port</span>
          <input
            type="number"
            min={1}
            max={65535}
            value={draft.smtp_port}
            onChange={(e) => setDraft({ ...draft, smtp_port: Number(e.target.value) })}
          />
        </label>
        <label className="settings-field settings-checkbox">
          <input
            type="checkbox"
            checked={draft.smtp_tls}
            onChange={(e) => setDraft({ ...draft, smtp_tls: e.target.checked })}
          />
          <span>Use STARTTLS</span>
        </label>
        <label className="settings-field">
          <span>Username</span>
          <input type="text" value={draft.smtp_username} onChange={(e) => setStr('smtp_username', e.target.value)} />
        </label>
        <label className="settings-field">
          <span>Password</span>
          <input type="password" value={draft.smtp_password} onChange={(e) => setStr('smtp_password', e.target.value)} />
        </label>
        <label className="settings-field">
          <span>Recipients (comma-separated)</span>
          <input
            type="text"
            value={draft.email_to.join(', ')}
            onChange={(e) => setDraft({ ...draft, email_to: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })}
          />
        </label>
        <label className="settings-field">
          <span>Public app URL (for links in emails)</span>
          <input type="text" value={draft.app_public_url} onChange={(e) => setStr('app_public_url', e.target.value)} />
        </label>

        <h3>Review reminder schedule</h3>
        <div className="settings-row">
          <label className="settings-field">
            <span>Hour</span>
            <input
              type="number"
              min={0}
              max={23}
              value={draft.review_reminder_hour}
              onChange={(e) => setDraft({ ...draft, review_reminder_hour: Number(e.target.value) })}
            />
          </label>
          <label className="settings-field">
            <span>Minute</span>
            <input
              type="number"
              min={0}
              max={59}
              value={draft.review_reminder_minute}
              onChange={(e) => setDraft({ ...draft, review_reminder_minute: Number(e.target.value) })}
            />
          </label>
        </div>

        {error && <div role="alert" className="settings-error">{error}</div>}
        <button type="submit" disabled={dirtyKeys.length === 0 || patch.isPending}>
          {patch.isPending ? 'Saving…' : 'Save'}
        </button>
      </form>

      <article className="settings-card">
        <h3>Send test email</h3>
        <p className="settings-help">
          Sends a test message to the configured recipients to verify SMTP works.
        </p>
        <button type="button" onClick={testNow} disabled={test.isPending}>
          {test.isPending ? 'Sending…' : 'Send test email'}
        </button>
        {testError && <div role="alert" className="settings-error">{testError}</div>}
        {testResult && <p className="settings-success">{testResult}</p>}
      </article>
    </section>
  );
}
