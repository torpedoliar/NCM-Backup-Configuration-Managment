import { useState } from 'react';
import type { FormEvent } from 'react';
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '../../api/hooks';
import type { ApiKeyCreated, ApiKeyRecord } from '../../api/types';
import { humanizeError } from '../../lib/errors';
import { formatTzDateTime } from '../../lib/fmt';

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
  { method: 'GET', path: '/api/v1/network-doc', purpose: 'Structured docs for all active switches (API key)' },
  { method: 'GET', path: '/api/v1/network-doc/{switch_id}', purpose: 'Structured doc for one switch (API key)' },
  { method: 'POST', path: '/api/v1/api-keys', purpose: 'Create API key — plaintext returned once (admin JWT)' },
  { method: 'GET', path: '/api/v1/api-keys', purpose: 'List API keys (admin JWT)' },
  { method: 'DELETE', path: '/api/v1/api-keys/{id}', purpose: 'Revoke API key (admin JWT)' },
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

  if (!keys) return <p>Loading…</p>;
  if (keys.length === 0) return <p className="settings-help">No API keys yet — create one above.</p>;

  function handleRevoke(key: ApiKeyRecord) {
    if (window.confirm(`Revoke API key "${key.name}"? Requests using it will be rejected immediately.`)) {
      revoke.mutate(key.id);
    }
  }

  return (
    <div>
      {keys.map((key) => (
        <div className="key-row" key={key.id}>
          <div>
            <strong>{key.name}</strong>
            <span className="key-meta">
              {key.prefix}… · created {formatTzDateTime(key.created_at)} ·{' '}
              {key.last_used_at ? `last used ${formatTzDateTime(key.last_used_at)}` : 'never used'}
            </span>
          </div>
          <span className={key.revoked ? 'key-status revoked' : 'key-status'}>
            {key.revoked ? 'REVOKED' : 'ACTIVE'}
          </span>
          {!key.revoked && (
            <button onClick={() => handleRevoke(key)} disabled={revoke.isPending}>
              Revoke
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

export function SettingsApiSection() {
  const create = useCreateApiKey();
  const [name, setName] = useState('');
  const [revealed, setRevealed] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleCreate(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setError(null);
    setRevealed(null);
    setCopied(false);
    create.mutate(trimmed, {
      onSuccess: (key) => {
        setRevealed(key);
        setName('');
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
          The REST API exposes structured network documentation — per-switch identity, VLAN table and port
          configuration parsed from the latest successful backup — for external tools. Read-only, authenticated
          with API keys. Port 8443 is the default; use the port shown in the Service tab if changed.
        </p>
        <h4>Authentication</h4>
        <p className="settings-help">
          Send your API key as <code>X-API-Key: &lt;key&gt;</code> or <code>Authorization: Bearer &lt;key&gt;</code>.
          Keys are shown in full only once, at creation. If a key leaks, revoke it here and create a new one.
        </p>
        <EndpointList />
        <pre className="settings-code">{CURL_EXAMPLES}</pre>
        <p className="settings-help">
          Each entry is built from the latest <em>successful</em> backup. Degraded output is reported in{' '}
          <code>parse_warnings</code> (e.g. <code>["no successful backup"]</code>) with an HTTP 200 — a bad backup
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
              placeholder="e.g. netbox-collector"
              required
            />
          </label>
          <button type="submit" disabled={create.isPending || !name.trim()}>
            {create.isPending ? 'Creating…' : 'Create key'}
          </button>
        </form>
        {error && (
          <div role="alert" className="settings-error">{error}</div>
        )}
        {revealed && (
          <div className="api-reveal">
            <p className="settings-help">Copy this key now — it will never be shown again.</p>
            <code className="key">{revealed.key}</code>
            <div>
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
