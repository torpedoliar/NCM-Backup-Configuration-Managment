import { useEffect, useState } from 'react';
import { useDecodedBackup, useFilteredBackups, useSwitches } from '../api/hooks';
import { humanizeError } from '../lib/errors';
import { formatTzDateTime } from '../lib/fmt';

export function DecodePage() {
  const { data: switches = [] } = useSwitches();
  const [switchId, setSwitchId] = useState<number | null>(null);
  const { data: backups = [] } = useFilteredBackups(switchId ? { switch_id: switchId } : { switch_id: -1 });
  const [backupId, setBackupId] = useState<number | null>(null);
  const { data: decoded, isFetching, error } = useDecodedBackup(backupId);

  useEffect(() => {
    if (switches.length > 0 && switchId === null) setSwitchId(switches[0].id);
  }, [switches, switchId]);

  useEffect(() => {
    if (backupId === null && backups.length > 0) setBackupId(backups[0].id);
    if (backupId !== null && !backups.some((b) => b.id === backupId)) setBackupId(backups[0]?.id ?? null);
  }, [backups, backupId]);

  return (
    <main>
      <p className="marker">/07 · DECODE</p>
      <h1 className="headline">Backups, decoded.</h1>

      <section className="filter-bar">
        <label>
          Switch
          <select value={switchId ?? ''} onChange={(e) => setSwitchId(Number(e.target.value))}>
            {switches.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label>
          Backup
          <select value={backupId ?? ''} disabled={backups.length === 0} onChange={(e) => setBackupId(Number(e.target.value))}>
            {backups.map((b) => <option key={b.id} value={b.id}>#{b.id} — {formatTzDateTime(b.created_at)}{b.success ? '' : ' (failed)'}</option>)}
          </select>
        </label>
      </section>

      {backups.length === 0 && switchId !== null ? <p>No backups for this switch.</p> : null}
      {error ? <div role="alert">{humanizeError(error)}</div> : null}
      {isFetching && !decoded ? <p>Decoding…</p> : null}

      {decoded ? (
        <section className="page-stack">
          <dl className="settings-list">
            <div><dt>Switch</dt><dd>{decoded.switch_name} · {decoded.protocol || '—'} · {decoded.dialect}</dd></div>
            <div><dt>Hostname</dt><dd>{decoded.hostname ?? '—'}</dd></div>
            <div><dt>Backup</dt><dd>#{decoded.backup_id} — {formatTzDateTime(decoded.backup_taken_at)}</dd></div>
          </dl>

          {decoded.parse_warnings.length > 0 ? (
            <div role="alert" className="settings-error">
              {decoded.parse_warnings.map((w) => <div key={w}>{w}</div>)}
            </div>
          ) : null}

          {decoded.vlans.length > 0 ? (
            <section>
              <h2>VLANs ({decoded.vlans.length})</h2>
              <div className="vlan-grid">
                {decoded.vlans.map((v) => (
                  <span className="vlan-chip" key={v.id}>{v.id}{v.name ? ` · ${v.name}` : ''}</span>
                ))}
              </div>
            </section>
          ) : null}

          {decoded.ports.length > 0 ? (
            <section>
              <h2>Ports ({decoded.ports.length})</h2>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Port</th>
                      <th>Description</th>
                      <th>Mode</th>
                      <th>Native</th>
                      <th>Access</th>
                      <th>Trunk allowed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {decoded.ports.map((p) => (
                      <tr key={p.name}>
                        <td><code>{p.name}</code> {p.enabled ? '' : <span className="key-status revoked">SHUT</span>}</td>
                        <td>{p.description ?? '—'}</td>
                        <td>{p.mode}</td>
                        <td>{p.native_vlan ?? '—'}</td>
                        <td>{p.access_vlan ?? '—'}</td>
                        <td>{p.trunk_allowed_vlans.length > 0 ? p.trunk_allowed_vlans.join(', ') : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
