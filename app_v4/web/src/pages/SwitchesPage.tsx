import { useMemo, useState } from 'react';
import {
  useCreateCredential,
  useCreateSwitch,
  useCredentials,
  useDeactivateSwitch,
  useActivateSwitch,
  useDeleteSwitch,
  useSwitches,
  useTriggerBackup,
  useUpdateSwitch,
} from '../api/hooks';
import { CredentialCombo } from '../components/CredentialCombo';
import type { SwitchRecord } from '../api/types';

const PROTOCOLS = ['ssh', 'telnet', 'websmart'] as const;
const DEFAULT_PORT: Record<string, number> = { ssh: 22, telnet: 23, websmart: 443 };

interface DraftSwitch {
  id: number | null;
  name: string;
  ip: string;
  protocol: string;
  port: number;
  credential_id: number | null;
  notes: string;
}

const EMPTY: DraftSwitch = { id: null, name: '', ip: '', protocol: 'ssh', port: 22, credential_id: null, notes: '' };

export function SwitchesPage() {
  const [showInactive, setShowInactive] = useState(false);
  const [draft, setDraft] = useState<DraftSwitch | null>(null);
  const [showNewCred, setShowNewCred] = useState(false);
  const [newCred, setNewCred] = useState({ name: '', username: '', password: '', enable_password: '' });

  const { data: switches = [] } = useSwitches();
  const { data: credentials = [] } = useCredentials();
  const create = useCreateSwitch();
  const update = useUpdateSwitch();
  const deactivate = useDeactivateSwitch();
  const activate = useActivateSwitch();
  const remove = useDeleteSwitch();
  const backup = useTriggerBackup();
  const createCred = useCreateCredential();

  const visible = useMemo(
    () => (showInactive ? switches : switches.filter((s) => s.is_active)),
    [switches, showInactive],
  );

  function startAdd() {
    setDraft({ ...EMPTY });
    setShowNewCred(false);
  }
  function startEdit(sw: SwitchRecord) {
    setDraft({
      id: sw.id,
      name: sw.name,
      ip: sw.ip,
      protocol: sw.protocol,
      port: sw.port,
      credential_id: sw.credential_id,
      notes: sw.notes ?? '',
    });
  }
  function cancel() {
    setDraft(null);
    setShowNewCred(false);
  }
  async function save() {
    if (!draft) return;
    let credId = draft.credential_id;
    if (showNewCred) {
      const created = await createCred.mutateAsync(newCred);
      credId = created.id;
    }
    if (credId === null) return;
    const payload = { name: draft.name, ip: draft.ip, protocol: draft.protocol, port: draft.port, credential_id: credId, notes: draft.notes };
    if (draft.id === null) {
      create.mutate(payload, { onSuccess: () => cancel() });
    } else {
      update.mutate({ id: draft.id, input: payload }, { onSuccess: () => cancel() });
    }
  }

  return (
    <main>
      <header className="page-header">
        <p className="marker">/02 · INV</p>
        <h1 className="headline">Inventory, sharpened for operators.</h1>
        <div className="page-actions">
          <label>
            <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
            Show inactive
          </label>
          <button onClick={startAdd} disabled={draft !== null}>+ Add switch</button>
        </div>
      </header>

      <table className="data-table">
        <thead>
          <tr><th>Name</th><th>Host</th><th>Protocol</th><th>Port</th><th>Credential</th><th>State</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {draft && draft.id === null && (
            <DraftRow
              draft={draft} setDraft={setDraft}
              credentials={credentials}
              showNewCred={showNewCred} setShowNewCred={setShowNewCred}
              newCred={newCred} setNewCred={setNewCred}
              onSave={save} onCancel={cancel}
            />
          )}
          {visible.map((sw) =>
            draft && draft.id === sw.id ? (
              <DraftRow
                key={sw.id}
                draft={draft} setDraft={setDraft}
                credentials={credentials}
                showNewCred={showNewCred} setShowNewCred={setShowNewCred}
                newCred={newCred} setNewCred={setNewCred}
                onSave={save} onCancel={cancel}
              />
            ) : (
              <tr key={sw.id} data-state={sw.is_active ? 'active' : 'inactive'}>
                <td>{sw.name} {!sw.is_active && <span className="badge badge-inactive">INACTIVE</span>}</td>
                <td>{sw.ip}</td>
                <td>{sw.protocol}</td>
                <td>{sw.port}</td>
                <td>{credentials.find((c) => c.id === sw.credential_id)?.name ?? '—'}</td>
                <td>{sw.is_active ? 'active' : 'inactive'}</td>
                <td className="row-actions">
                  <button onClick={() => startEdit(sw)} disabled={!sw.is_active}>Edit</button>
                  {sw.is_active ? (
                    <>
                      <button onClick={() => backup.mutate(sw.id)}>Backup now</button>
                      <button onClick={() => deactivate.mutate(sw.id)}>Deactivate</button>
                    </>
                  ) : (
                    <>
                      <button onClick={() => activate.mutate(sw.id)}>Activate</button>
                      <button
                        onClick={() => {
                          if (window.confirm(`Permanently delete ${sw.name}? Backup files will be preserved.`)) {
                            remove.mutate(sw.id);
                          }
                        }}
                      >
                        Delete
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </main>
  );
}

function DraftRow(props: {
  draft: DraftSwitch;
  setDraft: (d: DraftSwitch) => void;
  credentials: { id: number; name: string }[];
  showNewCred: boolean;
  setShowNewCred: (v: boolean) => void;
  newCred: { name: string; username: string; password: string; enable_password: string };
  setNewCred: (v: { name: string; username: string; password: string; enable_password: string }) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const { draft, setDraft, credentials, showNewCred, setShowNewCred, newCred, setNewCred, onSave, onCancel } = props;
  return (
    <>
      <tr className="draft-row">
        <td><input placeholder="Name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
        <td><input placeholder="Host/IP" value={draft.ip} onChange={(e) => setDraft({ ...draft, ip: e.target.value })} /></td>
        <td>
          <select value={draft.protocol} onChange={(e) => setDraft({ ...draft, protocol: e.target.value, port: DEFAULT_PORT[e.target.value] ?? draft.port })}>
            {PROTOCOLS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </td>
        <td><input type="number" value={draft.port} min={1} max={65535} onChange={(e) => setDraft({ ...draft, port: Number(e.target.value) })} /></td>
        <td>
          <CredentialCombo
            credentials={credentials as never}
            value={draft.credential_id}
            onChange={(id) => { setDraft({ ...draft, credential_id: id }); setShowNewCred(false); }}
            onCreateNew={() => setShowNewCred(true)}
          />
        </td>
        <td>—</td>
        <td className="row-actions">
          <button onClick={onSave}>Save</button>
          <button onClick={onCancel}>Cancel</button>
        </td>
      </tr>
      {showNewCred && (
        <tr className="draft-subrow">
          <td colSpan={7}>
            <fieldset>
              <legend>New credential</legend>
              <input placeholder="Name" value={newCred.name} onChange={(e) => setNewCred({ ...newCred, name: e.target.value })} />
              <input placeholder="Username" value={newCred.username} onChange={(e) => setNewCred({ ...newCred, username: e.target.value })} />
              <input type="password" placeholder="Password" value={newCred.password} onChange={(e) => setNewCred({ ...newCred, password: e.target.value })} />
              <input type="password" placeholder="Enable password (optional)" value={newCred.enable_password} onChange={(e) => setNewCred({ ...newCred, enable_password: e.target.value })} />
            </fieldset>
          </td>
        </tr>
      )}
    </>
  );
}
