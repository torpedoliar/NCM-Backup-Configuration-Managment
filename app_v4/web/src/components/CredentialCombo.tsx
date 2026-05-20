import type { CredentialRecord } from '../api/types';

const NEW_SENTINEL = '__new__';

export function CredentialCombo({
  credentials,
  value,
  onChange,
  onCreateNew,
}: {
  credentials: CredentialRecord[];
  value: number | null;
  onChange: (id: number) => void;
  onCreateNew: () => void;
}) {
  return (
    <select
      role="combobox"
      value={value === null ? '' : String(value)}
      onChange={(event) => {
        const v = event.target.value;
        if (v === NEW_SENTINEL) {
          onCreateNew();
        } else if (v !== '') {
          onChange(Number(v));
        }
      }}
    >
      <option value="" disabled>
        Select credential…
      </option>
      {credentials.map((c) => (
        <option key={c.id} value={c.id}>
          {c.name}
        </option>
      ))}
      <option value={NEW_SENTINEL}>+ New credential</option>
    </select>
  );
}
