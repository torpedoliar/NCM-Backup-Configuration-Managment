import { useEffect, useState } from 'react';
import { usePatchRetention, useRetention } from '../../api/hooks';
import type { RetentionSettings } from '../../api/types';

const FIELDS: { key: keyof RetentionSettings; label: string; min: number; max?: number }[] = [
  { key: 'backup_min_keep', label: 'Backup minimum keep', min: 1 },
  { key: 'backup_retention_days', label: 'Backup retention (days)', min: 7 },
  { key: 'audit_retention_days', label: 'Audit retention (days)', min: 7 },
  { key: 'retention_hour', label: 'Sweep hour', min: 0, max: 23 },
  { key: 'retention_minute', label: 'Sweep minute', min: 0, max: 59 },
];

export function SettingsRetentionSection() {
  const { data } = useRetention();
  const patch = usePatchRetention();
  const [draft, setDraft] = useState<RetentionSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) setDraft({ ...data });
  }, [data]);

  if (!draft || !data) return <p>Loading…</p>;

  const dirtyKeys = (Object.keys(draft) as (keyof RetentionSettings)[]).filter(
    (key) => draft[key] !== data[key],
  );

  function save() {
    setError(null);
    if (!data) return;
    const updates: Partial<RetentionSettings> = {};
    for (const key of dirtyKeys) {
      (updates as Record<string, number>)[key] = draft![key];
    }
    patch.mutate(updates, {
      onError: (err: unknown) => setError(err instanceof Error ? err.message : 'Save failed'),
    });
  }

  return (
    <section>
      <h2>Retention</h2>
      <form
        className="settings-form"
        onSubmit={(event) => {
          event.preventDefault();
          save();
        }}
      >
        {FIELDS.map((field) => (
          <label key={field.key} className="settings-field">
            <span>{field.label}</span>
            <input
              type="number"
              min={field.min}
              max={field.max}
              value={draft[field.key]}
              onChange={(event) => setDraft({ ...draft, [field.key]: Number(event.target.value) })}
            />
          </label>
        ))}
        {error && <div role="alert" className="settings-error">{error}</div>}
        <button type="submit" disabled={dirtyKeys.length === 0 || patch.isPending}>
          {patch.isPending ? 'Saving…' : 'Save'}
        </button>
      </form>
    </section>
  );
}
