import { useEffect, useState } from 'react';
import { useAuthSettings, usePatchAuthSettings } from '../../api/hooks';
import type { AuthSettings } from '../../api/types';
import { humanizeError } from '../../lib/errors';

type CardKey = 'token' | 'lockout' | 'password';

const FIELDS_BY_CARD: Record<CardKey, (keyof AuthSettings)[]> = {
  token: ['access_token_minutes', 'refresh_token_days'],
  lockout: ['lockout_threshold', 'lockout_window_minutes', 'lockout_duration_minutes'],
  password: [
    'password_min_length',
    'password_require_upper',
    'password_require_lower',
    'password_require_digit',
    'password_require_symbol',
  ],
};

const FIELD_LABEL: Record<keyof AuthSettings, string> = {
  access_token_minutes: 'Access token (minutes)',
  refresh_token_days: 'Refresh token (days)',
  lockout_threshold: 'Failed attempts threshold (0 = disabled)',
  lockout_window_minutes: 'Failure window (minutes)',
  lockout_duration_minutes: 'Lockout duration (minutes)',
  password_min_length: 'Min length',
  password_require_upper: 'Require uppercase',
  password_require_lower: 'Require lowercase',
  password_require_digit: 'Require digit',
  password_require_symbol: 'Require symbol',
};

export function SettingsAuthSection() {
  const { data } = useAuthSettings();
  const patch = usePatchAuthSettings();
  const [draft, setDraft] = useState<AuthSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) setDraft({ ...data });
  }, [
    data?.access_token_minutes,
    data?.refresh_token_days,
    data?.lockout_threshold,
    data?.lockout_window_minutes,
    data?.lockout_duration_minutes,
    data?.password_min_length,
    data?.password_require_upper,
    data?.password_require_lower,
    data?.password_require_digit,
    data?.password_require_symbol,
  ]);

  if (!draft || !data) return <p>Loading…</p>;

  function dirtyKeys(card: CardKey): (keyof AuthSettings)[] {
    return FIELDS_BY_CARD[card].filter((key) => draft![key] !== data![key]);
  }

  function saveCard(card: CardKey) {
    if (!data || !draft) return;
    setError(null);
    const updates: Partial<AuthSettings> = {};
    for (const key of dirtyKeys(card)) {
      (updates as Record<string, AuthSettings[keyof AuthSettings]>)[key] = draft[key];
    }
    patch.mutate(updates, {
      onError: (err: unknown) => setError(humanizeError(err)),
    });
  }

  function setField<K extends keyof AuthSettings>(key: K, value: AuthSettings[K]) {
    setDraft({ ...draft!, [key]: value });
  }

  function renderField(key: keyof AuthSettings) {
    const value = draft![key];
    if (typeof value === 'boolean') {
      return (
        <label key={key} className="settings-field">
          <input
            type="checkbox"
            checked={value}
            onChange={(event) => setField(key, event.target.checked as AuthSettings[typeof key])}
          />
          <span>{FIELD_LABEL[key]}</span>
        </label>
      );
    }
    return (
      <label key={key} className="settings-field">
        <span>{FIELD_LABEL[key]}</span>
        <input
          type="number"
          value={value as number}
          onChange={(event) => setField(key, Number(event.target.value) as AuthSettings[typeof key])}
        />
      </label>
    );
  }

  function renderCard(card: CardKey, title: string) {
    const dirty = dirtyKeys(card);
    return (
      <article className="settings-card">
        <h3>{title}</h3>
        {FIELDS_BY_CARD[card].map(renderField)}
        <button onClick={() => saveCard(card)} disabled={dirty.length === 0 || patch.isPending}>
          {patch.isPending ? 'Saving…' : 'Save'}
        </button>
      </article>
    );
  }

  return (
    <section>
      <h2>Authentication</h2>
      {error && <div role="alert" className="settings-error">{error}</div>}
      {renderCard('token', 'Token Lifetime')}
      {renderCard('lockout', 'Account Lockout')}
      {renderCard('password', 'Password Policy')}
    </section>
  );
}
