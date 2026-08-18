import { Fragment, useState } from 'react';
import {
  useCreateUser,
  useDeleteUser,
  useResetUserPassword,
  useUpdateUser,
  useUsers,
} from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import type { Role } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';

const ROLES: Role[] = ['admin', 'operator', 'viewer'];

interface DraftUser {
  id: number | null;
  username: string;
  role: Role;
  password: string;
  is_active: boolean;
}

const EMPTY_DRAFT: DraftUser = {
  id: null,
  username: '',
  role: 'viewer',
  password: '',
  is_active: true,
};

export function UsersPage() {
  const auth = useAuth();
  const myId = auth.user?.id ?? null;
  const [draft, setDraft] = useState<DraftUser | null>(null);
  const [resetingUserId, setResetingUserId] = useState<number | null>(null);
  const [newPwd, setNewPwd] = useState('');

  const { data: users = [] } = useUsers();
  const create = useCreateUser();
  const update = useUpdateUser();
  const remove = useDeleteUser();
  const resetPwd = useResetUserPassword();

  function startAdd() {
    setDraft({ ...EMPTY_DRAFT });
  }

  function startEdit(user: { id: number; username: string; role: Role; is_active: boolean }) {
    setDraft({
      id: user.id,
      username: user.username,
      role: user.role,
      password: '',
      is_active: user.is_active,
    });
  }

  function cancel() {
    setDraft(null);
  }

  function save() {
    if (!draft) return;
    if (draft.id === null) {
      create.mutate(
        { username: draft.username, role: draft.role, password: draft.password, is_active: draft.is_active },
        { onSuccess: cancel },
      );
    } else {
      update.mutate(
        { id: draft.id, input: { username: draft.username, role: draft.role, is_active: draft.is_active } },
        { onSuccess: cancel },
      );
    }
  }

  async function submitReset(userId: number) {
    await resetPwd.mutateAsync({ id: userId, password: newPwd });
    setResetingUserId(null);
    setNewPwd('');
  }

  return (
    <main>
      <header className="page-header">
        <p className="marker">/07 · USERS</p>
        <h1 className="headline">Access is operational control.</h1>
        <div className="page-actions">
          <button onClick={startAdd} disabled={draft !== null}>+ Add user</button>
        </div>
      </header>

      <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Username</th><th>Role</th><th>Active</th><th>Created</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {draft && draft.id === null && (
            <DraftUserRow draft={draft} setDraft={setDraft} onSave={save} onCancel={cancel} isNew />
          )}
          {users.map((u) =>
            draft && draft.id === u.id ? (
              <DraftUserRow key={u.id} draft={draft} setDraft={setDraft} onSave={save} onCancel={cancel} />
            ) : (
              <Fragment key={u.id}>
                <tr>
                  <td>{u.username}</td>
                  <td>{u.role}</td>
                  <td>
                    <input
                      type="checkbox"
                      aria-label="Active"
                      checked={u.is_active}
                      disabled={u.id === myId}
                      onChange={() => update.mutate({ id: u.id, input: { is_active: !u.is_active } })}
                    />
                  </td>
                  <td>{formatTzDateTime(u.created_at)}</td>
                  <td className="row-actions">
                    <button onClick={() => startEdit(u)}>Edit</button>
                    <button data-action="reset" onClick={() => setResetingUserId(u.id)}>
                      Reset password
                    </button>
                    <button
                      data-action="delete"
                      disabled={u.id === myId}
                      onClick={() => {
                        if (window.confirm(`Delete user ${u.username}?`)) remove.mutate(u.id);
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
                {resetingUserId === u.id && (
                  <tr className="draft-subrow">
                    <td colSpan={5}>
                      <input
                        type="password"
                        placeholder="New password"
                        value={newPwd}
                        onChange={(e) => setNewPwd(e.target.value)}
                      />
                      <button onClick={() => submitReset(u.id)}>Save new password</button>
                      <button onClick={() => { setResetingUserId(null); setNewPwd(''); }}>Cancel</button>
                    </td>
                  </tr>
                )}
              </Fragment>
            ),
          )}
        </tbody>
      </table>
      </div>
    </main>
  );
}

function DraftUserRow(props: {
  draft: DraftUser;
  setDraft: (d: DraftUser) => void;
  onSave: () => void;
  onCancel: () => void;
  isNew?: boolean;
}) {
  const { draft, setDraft, onSave, onCancel, isNew } = props;
  return (
    <tr className="draft-row">
      <td>
        <input
          placeholder="Username"
          value={draft.username}
          onChange={(e) => setDraft({ ...draft, username: e.target.value })}
        />
      </td>
      <td>
        <select value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value as Role })}>
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </td>
      <td>
        <input
          type="checkbox"
          checked={draft.is_active}
          onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })}
        />
      </td>
      <td>
        {isNew && (
          <input
            type="password"
            placeholder="Password"
            value={draft.password}
            onChange={(e) => setDraft({ ...draft, password: e.target.value })}
          />
        )}
      </td>
      <td className="row-actions">
        <button onClick={onSave}>Save</button>
        <button onClick={onCancel}>Cancel</button>
      </td>
    </tr>
  );
}
