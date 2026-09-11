import { useState } from 'react';
import type { FormEvent } from 'react';
import { useApiKeys, useCreateApiKey, useDeleteApiKey, useRevokeApiKey, useUpdateApiKey } from '../../api/hooks';
import type { ApiKeyCreated, ApiKeyRecord } from '../../api/types';
import { humanizeError } from '../../lib/errors';
import { formatTzDateTime } from '../../lib/fmt';

export const AVAILABLE_SCOPES = [
  { id: 'read', label: 'read', desc: 'Read switches, backups, baselines, reviews, & network-doc' },
  { id: 'switches:write', label: 'switches:write', desc: 'Create, update, delete, deactivate switches' },
  { id: 'credentials:write', label: 'credentials:write', desc: 'Create and update switch credentials' },
  { id: 'schedules:write', label: 'schedules:write', desc: 'Manage backup jobs & schedules' },
  { id: 'baselines:write', label: 'baselines:write', desc: 'Create, refresh, and delete config baselines' },
  { id: 'backup:write', label: 'backup:write', desc: 'Trigger on-demand backup tasks' },
  { id: 'reviews:write', label: 'reviews:write', desc: 'Approve, flag, and manage config drift reviews' },
  { id: 'system:write', label: 'system:write', desc: 'Push webhook & notification settings' },
] as const;

const CURL_EXAMPLES = `# List structured docs for all active switches
curl -H "X-API-Key: <your-key>" \\
  http://localhost:8443/api/v1/network-doc

# One switch by id (Bearer header works too)
curl -H "Authorization: Bearer <your-key>" \\
  http://localhost:8443/api/v1/network-doc/3`;

const SAMPLE_RESPONSE = `{
  "switch_id": 3,
  "name": "SW-CORE-01",
  "ip": "192.168.10.1",
  "protocol": "ssh",
  "hostname": "core01",
  "source_backup_id": 442,
  "backup_taken_at": "2026-08-18T04:00:00+00:00",
  "vlans": [ { "id": 88, "name": "IPH-DEVICE" } ],
  "ports": [ {
    "name": "port1.0.1",
    "description": "uplink",
    "enabled": true,
    "mode": "trunk",
    "native_vlan": 11,
    "access_vlan": null,
    "trunk_allowed_vlans": [ 88 ]
  } ],
  "parse_warnings": []
}`;

const ENDPOINTS = [
  { method: 'GET', path: '/api/v1/network-doc', purpose: 'Structured docs for all active switches (API key scope: read)' },
  { method: 'GET', path: '/api/v1/network-doc/{switch_id}', purpose: 'Structured doc for one switch (API key scope: read)' },
  { method: 'POST', path: '/api/v1/api-keys', purpose: 'Create API key with granular scopes (admin JWT)' },
  { method: 'PATCH', path: '/api/v1/api-keys/{id}', purpose: 'Update API key scopes (admin JWT)' },
  { method: 'GET', path: '/api/v1/api-keys', purpose: 'List API keys and their scopes (admin JWT)' },
  { method: 'DELETE', path: '/api/v1/api-keys/{id}', purpose: 'Revoke or delete API key (admin JWT)' },
];

function EndpointList() {
  return (
    <dl className="settings-list">
      {ENDPOINTS.map((e) => (
        <div key={e.method + e.path}>
          <dt>
            <code>{e.method}</code> <code>{e.path}</code>
          </dt>
          <dd>{e.purpose}</dd>
        </div>
      ))}
    </dl>
  );
}

function KeyList() {
  const { data: keys } = useApiKeys();
  const revoke = useRevokeApiKey();
  const remove = useDeleteApiKey();
  const updateKey = useUpdateApiKey();
  const [editingKeyId, setEditingKeyId] = useState<number | null>(null);
  const [editScopes, setEditScopes] = useState<string[]>([]);
  const [editError, setEditError] = useState<string | null>(null);

  if (!keys) return <p>Loading…</p>;
  if (keys.length === 0) return <p className="settings-help">No API keys yet — create one above.</p>;

  function handleRevoke(key: ApiKeyRecord) {
    if (window.confirm(`Revoke API key "${key.name}"? Requests using it will be rejected immediately.`)) {
      revoke.mutate(key.id);
    }
  }

  function handleDelete(key: ApiKeyRecord) {
    if (
      window.confirm(
        `Permanently delete API key "${key.name}"? The row is removed from the list; the audit log keeps the record. This cannot be undone.`,
      )
    ) {
      remove.mutate(key.id);
    }
  }

  function startEdit(key: ApiKeyRecord) {
    setEditingKeyId(key.id);
    setEditScopes(key.scopes || []);
    setEditError(null);
  }

  function toggleEditScope(scopeId: string) {
    setEditScopes((prev) =>
      prev.includes(scopeId) ? prev.filter((s) => s !== scopeId) : [...prev, scopeId],
    );
  }

  function handleSaveEdit(keyId: number) {
    setEditError(null);
    updateKey.mutate(
      { id: keyId, scopes: editScopes },
      {
        onSuccess: () => setEditingKeyId(null),
        onError: (err: unknown) => setEditError(humanizeError(err)),
      },
    );
  }

  return (
    <div>
      {keys.map((key) => {
        const isEditing = editingKeyId === key.id;
        const keyScopes = key.scopes || [];
        const isAllScopes = keyScopes.length === AVAILABLE_SCOPES.length;

        return (
          <div className="key-row" key={key.id} style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px 0', borderBottom: '1px solid var(--line-2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', width: '100%', gap: '12px' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong>{key.name}</strong>
                  <span className={key.revoked ? 'key-status revoked' : 'key-status'}>
                    {key.revoked ? 'REVOKED' : 'ACTIVE'}
                  </span>
                </div>
                <div className="key-meta" style={{ marginTop: '4px' }}>
                  {key.prefix}… · created {formatTzDateTime(key.created_at)} ·{' '}
                  {key.last_used_at ? `last used ${formatTzDateTime(key.last_used_at)}` : 'never used'}
                </div>
                <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', color: 'var(--muted, #94a3b8)', marginRight: '4px' }}>Scopes:</span>
                  {keyScopes.length > 0 ? (
                    isAllScopes ? (
                      <span style={{ backgroundColor: 'rgba(16, 185, 129, 0.2)', color: '#34d399', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>
                        DataGuard Full Access (All 8 scopes)
                      </span>
                    ) : (
                      keyScopes.map((s) => (
                        <span key={s} style={{ backgroundColor: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                          {s}
                        </span>
                      ))
                    )
                  ) : (
                    <span style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#f87171', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>
                      No Scopes (Legacy — 403 on API)
                    </span>
                  )}
                </div>
              </div>

              <div className="row-actions">
                {!key.revoked && (
                  <>
                    <button type="button" onClick={() => (isEditing ? setEditingKeyId(null) : startEdit(key))} disabled={updateKey.isPending}>
                      {isEditing ? 'Cancel' : 'Edit Scopes'}
                    </button>
                    <button type="button" onClick={() => handleRevoke(key)} disabled={revoke.isPending}>
                      Revoke
                    </button>
                  </>
                )}
                <button type="button" onClick={() => handleDelete(key)} disabled={remove.isPending}>
                  Delete
                </button>
              </div>
            </div>

            {isEditing && (
              <div style={{ marginTop: '8px', padding: '12px', background: 'var(--surface, #1e293b)', borderRadius: '6px', border: '1px solid var(--line-2)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--bone)' }}>Update Scopes for &quot;{key.name}&quot;</span>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button type="button" style={{ padding: '2px 8px', fontSize: '11px' }} onClick={() => setEditScopes(AVAILABLE_SCOPES.map((s) => s.id))}>
                      Select All (DataGuard)
                    </button>
                    <button type="button" style={{ padding: '2px 8px', fontSize: '11px' }} onClick={() => setEditScopes(['read'])}>
                      Read-Only
                    </button>
                    <button type="button" style={{ padding: '2px 8px', fontSize: '11px' }} onClick={() => setEditScopes([])}>
                      Clear
                    </button>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '6px', margin: '8px 0' }}>
                  {AVAILABLE_SCOPES.map((s) => (
                    <label key={s.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={editScopes.includes(s.id)}
                        onChange={() => toggleEditScope(s.id)}
                      />
                      <div>
                        <code style={{ fontSize: '11px', color: 'var(--amber, #f59e0b)' }}>{s.label}</code>
                        <div style={{ fontSize: '10px', color: 'var(--muted, #94a3b8)' }}>{s.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>

                {editError && <div role="alert" className="settings-error" style={{ margin: '6px 0' }}>{editError}</div>}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
                  <button type="button" onClick={() => setEditingKeyId(null)} disabled={updateKey.isPending}>
                    Cancel
                  </button>
                  <button type="button" onClick={() => handleSaveEdit(key.id)} disabled={updateKey.isPending} style={{ borderColor: 'var(--amber)', color: 'var(--amber)' }}>
                    {updateKey.isPending ? 'Saving…' : 'Save Scopes'}
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function SettingsApiSection() {
  const create = useCreateApiKey();
  const [name, setName] = useState('');
  const [scopes, setScopes] = useState<string[]>(AVAILABLE_SCOPES.map((s) => s.id));
  const [revealed, setRevealed] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleScope(scopeId: string) {
    setScopes((prev) =>
      prev.includes(scopeId) ? prev.filter((s) => s !== scopeId) : [...prev, scopeId],
    );
  }

  function handleCreate(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setError(null);
    setRevealed(null);
    setCopied(false);
    create.mutate({ name: trimmed, scopes }, {
      onSuccess: (key) => {
        setRevealed(key);
        setName('');
        setScopes(AVAILABLE_SCOPES.map((s) => s.id));
      },
      onError: (err: unknown) => setError(humanizeError(err)),
    });
  }

  async function handleCopy() {
    if (!revealed) return;
    await navigator.clipboard?.writeText(revealed.key);
    setCopied(true);
  }

  return (
    <section>
      <h2>API</h2>

      <article className="settings-card">
        <h3>Using the API</h3>
        <p className="settings-help">
          The REST API exposes structured network documentation and remote operations — per-switch identity, VLAN table, port
          configuration, config backups, reviews, baselines, and webhooks. Authenticated
          with granular scoped API keys. Port 8443 is the default; use the port shown in the Service tab if changed.
        </p>
        <h4>Authentication</h4>
        <p className="settings-help">
          Send your API key as <code>X-API-Key: &lt;key&gt;</code> or <code>Authorization: Bearer &lt;key&gt;</code>.
          Keys are shown in full only once, at creation. Ensure your key has the necessary scopes for integration.
        </p>
        <EndpointList />
        <pre className="settings-code">{CURL_EXAMPLES}</pre>
        <p className="settings-help">
          Each entry is built from the latest <em>successful</em> backup. Degraded output is reported in{' '}
          <code>parse_warnings</code> (e.g. <code>[&quot;no successful backup&quot;]</code>) with an HTTP 200 — a bad backup
          never breaks the bulk response. Supported dialects: AlliedWare Plus CLI, Dell-style CLI, WebSmart SNMP
          dump (V1/V2).
        </p>
        <pre className="settings-code">{SAMPLE_RESPONSE}</pre>
      </article>

      <article className="settings-card">
        <h3>Create API Key</h3>
        <form className="settings-form" onSubmit={handleCreate}>
          <label className="settings-field">
            <span>Key name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. dataguard-production"
              required
            />
          </label>

          <div style={{ marginTop: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--bone)' }}>Permissions &amp; Scopes</span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button type="button" style={{ padding: '2px 8px', fontSize: '11px' }} onClick={() => setScopes(AVAILABLE_SCOPES.map((s) => s.id))}>
                  DataGuard Full Access
                </button>
                <button type="button" style={{ padding: '2px 8px', fontSize: '11px' }} onClick={() => setScopes(['read'])}>
                  Read-Only
                </button>
                <button type="button" style={{ padding: '2px 8px', fontSize: '11px' }} onClick={() => setScopes([])}>
                  Clear
                </button>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '8px', marginTop: '8px', padding: '10px', background: 'var(--surface, #1e293b)', borderRadius: '6px', border: '1px solid var(--line-2)' }}>
              {AVAILABLE_SCOPES.map((s) => (
                <label key={s.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={scopes.includes(s.id)}
                    onChange={() => toggleScope(s.id)}
                  />
                  <div>
                    <code style={{ fontSize: '12px', color: 'var(--amber, #f59e0b)' }}>{s.label}</code>
                    <div style={{ fontSize: '11px', color: 'var(--muted, #94a3b8)', marginTop: '2px' }}>{s.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div style={{ marginTop: '14px' }}>
            <button type="submit" disabled={create.isPending || !name.trim()}>
              {create.isPending ? 'Creating…' : 'Create key'}
            </button>
          </div>
        </form>
        {error && (
          <div role="alert" className="settings-error">{error}</div>
        )}
        {revealed && (
          <div className="api-reveal">
            <p className="settings-help">Copy this key now — it will never be shown again.</p>
            <code className="key">{revealed.key}</code>
            <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--muted, #94a3b8)' }}>
              Granted scopes: <strong>{revealed.scopes?.join(', ') || 'none'}</strong>
            </div>
            <div style={{ marginTop: '10px' }}>
              <button type="button" onClick={() => void handleCopy()}>{copied ? 'Copied' : 'Copy'}</button>
              <button type="button" onClick={() => setRevealed(null)}>Done</button>
            </div>
          </div>
        )}
      </article>

      <article className="settings-card">
        <h3>API Keys</h3>
        <KeyList />
      </article>
    </section>
  );
}
