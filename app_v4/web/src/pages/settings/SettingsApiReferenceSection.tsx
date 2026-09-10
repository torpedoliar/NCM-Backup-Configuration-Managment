import { API_REF, CURL_EXAMPLES, ENDPOINT_DESCRIPTIONS, KNOWN_SCOPES, LEGACY_KEY_NOTE, WEBHOOK_EVENT_MAP, WEBHOOK_SIGNATURE } from '../../api/apiReference';

const METHOD_ORDER: Record<string, number> = { GET: 0, POST: 1, PATCH: 2, PUT: 3, DELETE: 4 };

const MODULE_TITLES: Record<string, string> = {
  switches: 'Switches',
  backups: 'Backups',
  credentials: 'Credentials',
  jobs: 'Jobs / Schedules',
  'config-reviews': 'Baselines & Reviews',
  'network-doc': 'Network Doc',
  system: 'System',
  'api-keys': 'API Keys',
  auth: 'Auth',
  users: 'Users',
  audit: 'Audit',
};

const MODULE_NOTES: Record<string, string> = {
  'network-doc':
    'Catatan tiket 16: /network-doc kini mengikuti pola scope — key lama (tanpa scope) ditolak 403. ' +
    'DataGuard dan konsumen lain harus memakai key dengan scope read (atau JWT). Lihat bagian Auth di bawah.',
  system:
    'Sebagian besar endpoint System hanya JWT (per user, sesuai peran). Satu-satunya penulisan lewat API key adalah ' +
    'PATCH notify-settings (webhook) dengan scope system:write — dipakai DataGuard untuk mengatur webhook per site.',
  auth: 'Login/refresh/logout tidak memakai credential header; kredensial ada di body. Semua endpoint lain mewajibkan JWT atau API key.',
};

function groupByTag() {
  const groups = new Map<string, typeof API_REF>();
  for (const e of API_REF) {
    const list = groups.get(e.tag) ?? [];
    list.push(e);
    groups.set(e.tag, list);
  }
  for (const list of groups.values()) {
    list.sort((a, b) => a.path.localeCompare(b.path) || (METHOD_ORDER[a.method] ?? 9) - (METHOD_ORDER[b.method] ?? 9));
  }
  return groups;
}

function endpointKey(e: { method: string; path: string }) {
  return `${e.method} ${e.path}`;
}

function describeAuth(auth: string): string {
  if (auth === 'public (no credentials)') return 'Publik — kredensial di body';
  if (auth.startsWith('JWT-or-key (scope: ')) {
    const scope = auth.slice('JWT-or-key (scope: '.length, -1);
    return `JWT (semua peran) atau API key scope ${scope}`;
  }
  if (auth.startsWith('JWT ') && auth.includes(' or key ')) {
    const [roles, scope] = auth.split(' or key ');
    return `JWT (${roles.replace(/^JWT /, '')}) atau API key scope ${scope}`;
  }
  if (auth === 'JWT (any role)') return 'JWT (semua peran)';
  return auth;
}

function EndpointTable({ tag }: { tag: string }) {
  const entries = groupByTag().get(tag) ?? [];
  return (
    <table className="api-ref-table">
      <thead>
        <tr>
          <th>Method</th>
          <th>Path</th>
          <th>Auth</th>
          <th>Deskripsi</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((e) => (
          <tr key={endpointKey(e)}>
            <td>
              <code className={`api-method api-method-${e.method.toLowerCase()}`}>{e.method}</code>
            </td>
            <td>
              <code>{e.path}</code>
            </td>
            <td className="api-auth">{describeAuth(e.auth)}</td>
            <td>{ENDPOINT_DESCRIPTIONS[endpointKey(e)] ?? e.summary}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function SettingsApiReferenceSection() {
  const tags = [...groupByTag().keys()];
  return (
    <section>
      <h2>API Reference</h2>
      <p className="settings-help">
        Referensi lengkap REST API NCM ({API_REF.length} endpoint, prefix <code>/api/v1</code>). Data digenerate dari
        router backend oleh <code>scripts/gen_api_reference.py</code> dan dijaga sinkron oleh pytest{' '}
        <code>test_api_reference_sync</code> — dokumen ini tidak bisa basi secara diam-diam.
      </p>

      {tags.map((tag) => (
        <article className="settings-card" key={tag}>
          <h3>{MODULE_TITLES[tag] ?? tag}</h3>
          {MODULE_NOTES[tag] ? <p className="settings-help">{MODULE_NOTES[tag]}</p> : null}
          <EndpointTable tag={tag} />
          {CURL_EXAMPLES.filter((c) => c.tag === tag).length > 0 && (
            <>
              <h4>Contoh curl</h4>
              {CURL_EXAMPLES.filter((c) => c.tag === tag).map((c) => (
                <div key={c.title}>
                  <p className="settings-help">{c.title}</p>
                  <pre className="settings-code">{c.code}</pre>
                </div>
              ))}
            </>
          )}
        </article>
      ))}

      <article className="settings-card">
        <h3>Autentikasi</h3>
        <p className="settings-help">
          Dua cara autentikasi: <strong>JWT</strong> dari <code>POST /auth/login</code> (header{' '}
          <code>Authorization: Bearer &lt;token&gt;</code>, hak mengikuti peran user) atau <strong>API key</strong>{' '}
          (header <code>X-API-Key: &lt;key&gt;</code>; <code>Authorization: Bearer</code> juga diterima), dengan hak
          sesuai scope key.
        </p>
        <h4>Scope API key</h4>
        <dl className="settings-list">
          {Object.entries(KNOWN_SCOPES).map(([scope, meaning]) => (
            <div key={scope}>
              <dt>
                <code>{scope}</code>
              </dt>
              <dd>{meaning}</dd>
            </div>
          ))}
        </dl>
        <p className="settings-help">{LEGACY_KEY_NOTE}</p>
      </article>

      <article className="settings-card">
        <h3>Webhook</h3>
        <p className="settings-help">
          NCM mengirim event ke URL webhook yang dikonfigurasi di Settings › Notifications (butuh admin JWT atau key
          scope system:write). Pemetaan event internal ke nama webhook:
        </p>
        <dl className="settings-list">
          {Object.entries(WEBHOOK_EVENT_MAP).map(([internal, names]) => (
            <div key={internal}>
              <dt>
                <code>{internal}</code>
              </dt>
              <dd>
                {names.map((n) => (
                  <code key={n}>{n} </code>
                ))}
              </dd>
            </div>
          ))}
        </dl>
        <p className="settings-help">{WEBHOOK_SIGNATURE}</p>
        <p className="settings-help">
          Contoh verifikasi (Node.js):{' '}
          <code>
            crypto.createHmac(&apos;sha256&apos;, secret).update(rawBody).digest(&apos;hex&apos;) ===
            header.slice(&apos;sha256=&apos;.length)
          </code>
        </p>
      </article>
    </section>
  );
}
