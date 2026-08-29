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
import { useOptionalAuth } from '../auth/AuthProvider';
import { humanizeError } from '../lib/errors';
import { CredentialCombo } from '../components/CredentialCombo';
import type { CredentialRecord, SwitchRecord } from '../api/types';

const PROTOCOLS = ['ssh', 'telnet', 'http', 'https', 'websmart', 'websmart-v2'] as const;
const DEFAULT_PORT: Record<string, number> = {
  ssh: 22,
  telnet: 23,
  http: 80,
  https: 443,
  websmart: 80,
  'websmart-v2': 80,
};

type SortKey = 'name' | 'name-desc' | 'ip' | 'protocol' | 'port';
const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'name', label: 'Name (A–Z)' },
  { value: 'name-desc', label: 'Name (Z–A)' },
  { value: 'ip', label: 'IP address' },
  { value: 'protocol', label: 'Protocol' },
  { value: 'port', label: 'Port' },
];

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
  const auth = useOptionalAuth();
  const isAdmin = auth?.user?.role === 'admin';
  const [showInactive, setShowInactive] = useState(false);
  const [draft, setDraft] = useState<DraftSwitch | null>(null);
  const [showNewCred, setShowNewCred] = useState(false);
  const [newCred, setNewCred] = useState({ name: '', username: '', password: '', enable_password: '' });
  const [saveError, setSaveError] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [proto, setProto] = useState('');
  const [sortBy, setSortBy] = useState<SortKey>('name');

  const { data: switches = [] } = useSwitches(showInactive);
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

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return visible.filter((sw) => {
      if (proto && sw.protocol !== proto) return false;
      if (!term) return true;
      const credName = credentials.find((c) => c.id === sw.credential_id)?.name ?? '';
      return (
        sw.name.toLowerCase().includes(term) ||
        sw.ip.toLowerCase().includes(term) ||
        sw.protocol.toLowerCase().includes(term) ||
        credName.toLowerCase().includes(term)
      );
    });
  }, [visible, q, proto, credentials]);

  const sorted = useMemo(() => {
    const list = filtered.slice();
    switch (sortBy) {
      case 'name-desc': list.sort((a, b) => b.name.localeCompare(a.name)); break;
      case 'ip': list.sort((a, b) => a.ip.localeCompare(b.ip, undefined, { numeric: true })); break;
      case 'protocol': list.sort((a, b) => a.protocol.localeCompare(b.protocol) || a.name.localeCompare(b.name)); break;
      case 'port': list.sort((a, b) => a.port - b.port); break;
      default: list.sort((a, b) => a.name.localeCompare(b.name));
    }
    return list;
  }, [filtered, sortBy]);

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
    setSaveError(null);
  }
  async function save() {
    if (!draft) return;
    setSaveError(null);
    if (showNewCred && !isAdmin) {
      // Backend rejects credential creation for non-admins; surface it early.
      setSaveError('Only admins can create new credentials.');
      return;
    }
    let credId = draft.credential_id;
    if (showNewCred) {
      try {
        const created = await createCred.mutateAsync(newCred);
        credId = created.id;
      } catch (err) {
        setSaveError(humanizeError(err));
        return;
      }
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

      {saveError ? <div role="alert" className="settings-error" style={{ margin: '8px 0' }}>{saveError}</div> : null}

      <section className="filter-bar">
        <label>
          Search
          <input
            placeholder="Name, IP, protocol…"
            value={q}
            onChange={(event) => setQ(event.target.value)}
          />
        </label>
        <label>
          Protocol
          <select value={proto} onChange={(event) => setProto(event.target.value)}>
            <option value="">All</option>
            {PROTOCOLS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label>
          Sort
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value as SortKey)}>
            {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      </section>

      <div className="table-wrap">
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
              allowCreate={isAdmin}
            />
          )}
          {sorted.map((sw) =>
            draft && draft.id === sw.id ? (
              <DraftRow
                key={sw.id}
                draft={draft} setDraft={setDraft}
                credentials={credentials}
                showNewCred={showNewCred} setShowNewCred={setShowNewCred}
                newCred={newCred} setNewCred={setNewCred}
                onSave={save} onCancel={cancel}
                allowCreate={isAdmin}
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
      </div>
    </main>
  );
}

function DraftRow(props: {
  draft: DraftSwitch;
  setDraft: (d: DraftSwitch) => void;
  credentials: CredentialRecord[];
  showNewCred: boolean;
  setShowNewCred: (v: boolean) => void;
  newCred: { name: string; username: string; password: string; enable_password: string };
  setNewCred: (v: { name: string; username: string; password: string; enable_password: string }) => void;
  onSave: () => void;
  onCancel: () => void;
  allowCreate?: boolean;
}) {
  const { draft, setDraft, credentials, showNewCred, setShowNewCred, newCred, setNewCred, onSave, onCancel, allowCreate = true } = props;
  const credentialReady = showNewCred
    ? !!newCred.name && !!newCred.username && !!newCred.password
    : draft.credential_id !== null;
  const canSave = !!draft.name && !!draft.ip && credentialReady;
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
            credentials={credentials}
            value={draft.credential_id}
            onChange={(id) => { setDraft({ ...draft, credential_id: id }); setShowNewCred(false); }}
            onCreateNew={() => setShowNewCred(true)}
            allowCreate={allowCreate}
          />
        </td>
        <td>—</td>
        <td className="row-actions">
          <button onClick={onSave} disabled={!canSave}>Save</button>
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
