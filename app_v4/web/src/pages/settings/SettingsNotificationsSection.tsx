import { useEffect, useState } from 'react';
import { useNotifySettings, usePatchNotifySettings, useTestNotify, useTestNotifyReminder } from '../../api/hooks';
import type { NotifySettings } from '../../api/types';
import { humanizeError } from '../../lib/errors';

const REMINDER_VARS = [
  '{{generated_at}}', '{{review_url}}', '{{total_switches}}', '{{baseline_coverage}}',
  '{{pending_count}}', '{{pending_reviews_html}}', '{{missing_count}}', '{{missing_baselines}}',
  '{{stale_count}}', '{{stale_baselines}}', '{{reviews_flagged}}',
  '{{reminder_review_count}}', '{{reminder_reviews_html}}', '{{review_interval_months}}',
] as const;

const DEFAULT_TEMPLATE_SNIPPET = `<!-- Kosongkan textarea ini untuk memakai template default bawaan. -->
<!-- Contoh kerangka custom (salin lalu edit): -->
<h2>Review reminder {{generated_at}}</h2>
<p>Coverage: {{baseline_coverage}}% dari {{total_switches}} switch.</p>
<h3>Pending reviews ({{pending_count}})</h3>
<table border="1" cellpadding="4">
  <tr><th>ID</th><th>Switch</th><th>Dibuat</th></tr>
{{pending_reviews_html}}
</table>
<p>Switch tanpa baseline ({{missing_count}}): {{missing_baselines}}</p>
<p>Stale >30 hari ({{stale_count}}): {{stale_baselines}}</p>
<p><a href="{{review_url}}">Buka review queue</a></p>`;

export function SettingsNotificationsSection() {
  const { data } = useNotifySettings();
  const patch = usePatchNotifySettings();
  const test = useTestNotify();
  const testReminder = useTestNotifyReminder();
  const [draft, setDraft] = useState<NotifySettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [reminderError, setReminderError] = useState<string | null>(null);
  const [reminderResult, setReminderResult] = useState<string | null>(null);

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

  function testReminderNow() {
    setReminderError(null);
    setReminderResult(null);
    testReminder.mutate(undefined, {
      onSuccess: (r) => setReminderResult(`Reminder preview sent (${r.channel}): ${r.subject}`),
      onError: (err: unknown) => setReminderError(humanizeError(err)),
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
        <h3>Event notifications</h3>
        <label className="settings-field settings-checkbox">
          <input
            type="checkbox"
            checked={draft.email_backup_failed}
            onChange={(e) => setDraft({ ...draft, email_backup_failed: e.target.checked })}
          />
          <span>Email saat backup GAGAL</span>
        </label>
        <label className="settings-field settings-checkbox">
          <input
            type="checkbox"
            checked={draft.email_backup_success}
            onChange={(e) => setDraft({ ...draft, email_backup_success: e.target.checked })}
          />
          <span>Email saat backup BERHASIL (opsi tambahan)</span>
        </label>
        <label className="settings-field settings-checkbox">
          <input
            type="checkbox"
            checked={draft.email_review_events}
            onChange={(e) => setDraft({ ...draft, email_review_events: e.target.checked })}
          />
          <span>Email event review (pending &amp; keputusan)</span>
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
        <p className="settings-help">
          Jam kirim email reminder harian. Interval bulanan review-nya (mis. tiap 6 bulan) diatur di
          halaman Baselines → "Review cycle".
        </p>
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
        <h3>Reminder email template (HTML)</h3>
        <p className="settings-help">
          Custom isi email review-reminder dengan variable di bawah — semuanya terisi otomatis dari
          data compliance saat email dikirim. Kosongkan textarea untuk memakai template default
          bawaan. Nilai teks otomatis di-escape; <code>{"{{pending_reviews_html}}"}</code> adalah
          blok baris tabel siap pakai.
        </p>
        <div className="settings-help">
          {REMINDER_VARS.map((v) => (
            <code key={v} style={{ display: 'inline-block', margin: '2px 6px 2px 0' }}>{v}</code>
          ))}
        </div>
        <label className="settings-field" style={{ minWidth: '100%' }}>
          <span>Template HTML</span>
          <textarea
            rows={14}
            spellCheck={false}
            placeholder={DEFAULT_TEMPLATE_SNIPPET}
            value={draft.email_template}
            onChange={(e) => setDraft({ ...draft, email_template: e.target.value })}
          />
        </label>
        <div className="row-actions">
          <button
            type="button"
            onClick={() => setDraft({ ...draft, email_template: '' })}
            title="Kosongkan = pakai template default bawaan"
          >
            Reset ke default
          </button>
          <button type="button" onClick={testReminderNow} disabled={testReminder.isPending}>
            {testReminder.isPending ? 'Sending…' : 'Kirim preview reminder'}
          </button>
        </div>
        {reminderError && <div role="alert" className="settings-error">{reminderError}</div>}
        {reminderResult && <p className="settings-success">{reminderResult}</p>}
      </article>

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
