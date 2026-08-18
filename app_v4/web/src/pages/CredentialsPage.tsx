import { useState } from 'react';
import {
  useCreateCredential,
  useCredentials,
  useDeleteCredential,
  useUpdateCredential,
} from '../api/hooks';
import type { CredentialUpdateInput } from '../api/types';
import { humanizeError } from '../lib/errors';

interface DraftCred {
  id: number | null;
  name: string;
  username: string;
  password: string;
  enable_password: string;
}

const EMPTY: DraftCred = { id: null, name: '', username: '', password: '', enable_password: '' };

export function CredentialsPage() {
  const [draft, setDraft] = useState<DraftCred | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: credentials = [] } = useCredentials();
  const create = useCreateCredential();
  const update = useUpdateCredential();
  const remove = useDeleteCredential();

  function startAdd() {
    setError(null);
    setDraft({ ...EMPTY });
  }

  function startEdit(c: { id: number; name: string; username?: string }) {
    setError(null);
    setDraft({ id: c.id, name: c.name, username: c.username ?? '', password: '', enable_password: '' });
  }

  function cancel() {
    setError(null);
    setDraft(null);
  }

  function save() {
    if (!draft) return;
    setError(null);
    if (draft.id === null) {
      create.mutate(
        { name: draft.name, username: draft.username, password: draft.password, enable_password: draft.enable_password || undefined },
        { onSuccess: cancel, onError: (err: unknown) => setError(humanizeError(err)) },
      );
    } else {
      // On update, only send fields that were typed (don't accidentally blank password).
      const input: CredentialUpdateInput = { name: draft.name, username: draft.username };
      if (draft.password) input.password = draft.password;
      if (draft.enable_password) input.enable_password = draft.enable_password;
      update.mutate({ id: draft.id, input }, { onSuccess: cancel, onError: (err: unknown) => setError(humanizeError(err)) });
    }
  }

  function handleDelete(c: { id: number; name: string }) {
    setError(null);
    if (window.confirm(`Delete credential ${c.name}?`)) {
      remove.mutate(c.id, { onError: (err: unknown) => setError(humanizeError(err)) });
    }
  }

  return (
    <main>
      <header className="page-header">
        <p className="marker">/03 · CREDS</p>
        <h1 className="headline">Credentials stay write-only.</h1>
        <div className="page-actions">
          <button onClick={startAdd} disabled={draft !== null}>+ Add credential</button>
        </div>
      </header>
      {error ? <div role="alert" className="settings-error">{error}</div> : null}

      <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr><th>Name</th><th>Username</th><th>Secret</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {draft && draft.id === null && (
            <DraftCredentialRow draft={draft} setDraft={setDraft} onSave={save} onCancel={cancel} isNew />
          )}
          {credentials.map((c) =>
            draft && draft.id === c.id ? (
              <DraftCredentialRow key={c.id} draft={draft} setDraft={setDraft} onSave={save} onCancel={cancel} />
            ) : (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.username ?? '—'}</td>
                <td>••••••••</td>
                <td className="row-actions">
                  <button onClick={() => startEdit(c)}>Edit</button>
                  <button onClick={() => handleDelete(c)}>
                    Delete
                  </button>
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
      </div>
    </main>
  );
}

function DraftCredentialRow(props: {
  draft: DraftCred;
  setDraft: (d: DraftCred) => void;
  onSave: () => void;
  onCancel: () => void;
  isNew?: boolean;
}) {
  const { draft, setDraft, onSave, onCancel, isNew } = props;
  return (
    <tr className="draft-row">
      <td>
        <input
          placeholder="Name"
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        />
      </td>
      <td>
        <input
          placeholder="Username"
          value={draft.username}
          onChange={(e) => setDraft({ ...draft, username: e.target.value })}
        />
      </td>
      <td>
        <input
          type="password"
          placeholder={isNew ? 'Password' : 'Password (leave blank to keep)'}
          value={draft.password}
          onChange={(e) => setDraft({ ...draft, password: e.target.value })}
        />
        <input
          type="password"
          placeholder="Enable password (optional)"
          value={draft.enable_password}
          onChange={(e) => setDraft({ ...draft, enable_password: e.target.value })}
        />
      </td>
      <td className="row-actions">
        <button onClick={onSave} disabled={isNew && (!draft.name || !draft.username || !draft.password)}>
          Save
        </button>
        <button onClick={onCancel}>Cancel</button>
      </td>
    </tr>
  );
}
