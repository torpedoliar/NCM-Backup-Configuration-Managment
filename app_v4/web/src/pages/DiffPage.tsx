import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useDecodedBackup, useFilteredBackups, useSwitches } from '../api/hooks';
import type { DecodedBackup, DecodePort, DecodeVlan } from '../api/types';
import { formatTzDateTime } from '../lib/fmt';
import { humanizeError } from '../lib/errors';

type SideBySideRow = {
  line_a: number;
  line_b: number;
  text_a: string;
  text_b: string;
  op: 'equal' | 'delete' | 'insert' | 'replace';
};

type DiffStats = {
  added_lines: number;
  removed_lines: number;
  changed_lines: number;
  total_changes: number;
};

type SideBySideResponse = {
  rows: SideBySideRow[];
  stats: DiffStats;
};

type ViewMode = 'side-by-side' | 'unified' | 'decode';

function seqLabel(b: { id: number; switch_seq?: number | null }): string {
  const seq = b.switch_seq != null ? b.switch_seq : `g#${b.id}`;
  return b.switch_seq != null ? `#${seq} (g#${b.id})` : `#${b.id}`;
}

/** Structured delta between two decoded configs (VLANs + ports). */
function decodeDelta(a: DecodedBackup, b: DecodedBackup) {
  const vlanKey = (v: DecodeVlan) => `${v.id}=${v.name}`;
  const vlansA = new Set(a.vlans.map(vlanKey));
  const vlansB = new Set(b.vlans.map(vlanKey));
  const vlans_added = [...b.vlans].filter((v) => !vlansA.has(vlanKey(v)));
  const vlans_removed = [...a.vlans].filter((v) => !vlansB.has(vlanKey(v)));

  const portKey = (p: DecodePort) =>
    [p.mode ?? '', p.native_vlan ?? '', p.access_vlan ?? '', (p.trunk_allowed_vlans ?? []).join(','), p.enabled ? 'up' : 'down'].join('|');
  const portsA = new Map(a.ports.map((p) => [p.name, { obj: p, key: portKey(p) }]));
  const portsB = new Map(b.ports.map((p) => [p.name, { obj: p, key: portKey(p) }]));
  const ports_changed: { name: string; from: DecodePort; to: DecodePort }[] = [];
  for (const [name, entryB] of portsB) {
    const entryA = portsA.get(name);
    if (entryA && entryA.key !== entryB.key) ports_changed.push({ name, from: entryA.obj, to: entryB.obj });
  }
  const ports_added = [...portsB.keys()].filter((n) => !portsA.has(n));
  const ports_removed = [...portsA.keys()].filter((n) => !portsB.has(n));
  const description_changed = a.ports
    .filter((pa) => portsB.has(pa.name))
    .filter((pa) => {
      const pb = portsB.get(pa.name);
      return pb && (pb.obj.description ?? '') !== (pa.description ?? '');
    })
    .map((pa) => pa.name);
  return { vlans_added, vlans_removed, ports_changed, ports_added, ports_removed, description_changed };
}

function PortDelta({ from, to }: { from: DecodePort; to: DecodePort }) {
  const fields: [string, string | number | boolean | null, string | number | boolean | null][] = [
    ['mode', from.mode, to.mode],
    ['native_vlan', from.native_vlan, to.native_vlan],
    ['access_vlan', from.access_vlan, to.access_vlan],
    ['trunk_allowed', (from.trunk_allowed_vlans ?? []).join(','), (to.trunk_allowed_vlans ?? []).join(',')],
    ['enabled', from.enabled, to.enabled],
    ['description', from.description ?? '', to.description ?? ''],
  ];
  const changed = fields.filter(([, f, t]) => String(f) !== String(t));
  return (
    <div className="review-note">
      <span className="marker">{from.name}</span>
      {changed.map(([field, f, t]) => (
        <p key={field}>
          <b>{field}</b>: <span className="diff-stat-removed">{String(f) || '—'}</span> →{' '}
          <span className="diff-stat-added">{String(t) || '—'}</span>
        </p>
      ))}
    </div>
  );
}

function DecodeView({ aId, bId }: { aId: number; bId: number }) {
  const { data: a, isLoading: la } = useDecodedBackup(aId);
  const { data: b, isLoading: lb } = useDecodedBackup(bId);

  if (la || lb) return <p className="viewer-empty">Decoding…</p>;
  if (!a || !b) return <p className="viewer-empty">Decode failed.</p>;

  const d = decodeDelta(a, b);
  const empty =
    d.vlans_added.length === 0 && d.vlans_removed.length === 0 && d.ports_changed.length === 0 &&
    d.ports_added.length === 0 && d.ports_removed.length === 0 && d.description_changed.length === 0;

  return (
    <section className="diff-side">
      <header className="diff-stats">
        <span className="diff-stat diff-stat-added">+{d.vlans_added.length + d.ports_added.length} added</span>
        <span className="diff-stat diff-stat-removed">−{d.vlans_removed.length + d.ports_removed.length} removed</span>
        <span className="diff-stat diff-stat-changed">~{d.ports_changed.length + d.description_changed.length} changed</span>
      </header>
      {a.hostname !== b.hostname ? (
        <div className="review-note">
          <span className="marker">hostname</span>
          <p><b>hostname</b>: <span className="diff-stat-removed">{a.hostname || '—'}</span> → <span className="diff-stat-added">{b.hostname || '—'}</span></p>
        </div>
      ) : null}
      {d.vlans_added.length > 0 && (
        <div className="review-note"><span className="marker">VLAN ditambahkan</span><p>{d.vlans_added.map((v) => `${v.id} (${v.name})`).join(', ')}</p></div>
      )}
      {d.vlans_removed.length > 0 && (
        <div className="review-note"><span className="marker">VLAN dihapus</span><p>{d.vlans_removed.map((v) => `${v.id} (${v.name})`).join(', ')}</p></div>
      )}
      {d.ports_changed.length > 0 && (
        <>
          <h3>Port berubah ({d.ports_changed.length})</h3>
          {d.ports_changed.map((pc) => <PortDelta key={pc.name} from={pc.from} to={pc.to} />)}
        </>
      )}
      {d.description_changed.length > 0 && (
        <>
          <h3>Description berubah</h3>
          {d.description_changed.map((name) => {
            const pa = a.ports.find((p) => p.name === name)!;
            const pb = b.ports.find((p) => p.name === name)!;
            return <PortDelta key={name} from={pa} to={pb} />;
          })}
        </>
      )}
      {d.ports_added.length > 0 && (
        <div className="review-note"><span className="marker">Port baru</span><p>{d.ports_added.join(', ')}</p></div>
      )}
      {d.ports_removed.length > 0 && (
        <div className="review-note"><span className="marker">Port hilang</span><p>{d.ports_removed.join(', ')}</p></div>
      )}
      {empty && a.hostname === b.hostname ? (
        <p className="viewer-empty">Konfigurasi struktural identik — perubahan hanya pada baris yang tidak ter-decode (mis. komentar/urutan).</p>
      ) : null}
      {(a.parse_warnings?.length ?? 0) > 0 || (b.parse_warnings?.length ?? 0) > 0 ? (
        <p className="settings-help">Parse warnings: {[...(a.parse_warnings ?? []), ...(b.parse_warnings ?? [])].join('; ')}</p>
      ) : null}
    </section>
  );
}

export function DiffPage() {
  const { data: switches = [] } = useSwitches();
  const [switchId, setSwitchId] = useState<number | null>(null);
  const { data: backups = [] } = useFilteredBackups(switchId ? { switch_id: switchId } : { switch_id: -1 });
  const [aId, setAId] = useState<number | null>(null);
  const [bId, setBId] = useState<number | null>(null);
  const [mode, setMode] = useState<ViewMode>('side-by-side');
  const [unified, setUnified] = useState('');
  const [sideBySide, setSideBySide] = useState<SideBySideResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (switches.length > 0 && switchId === null) setSwitchId(switches[0].id);
  }, [switches, switchId]);

  useEffect(() => {
    if (backups.length < 2) {
      setAId(null);
      setBId(null);
      return;
    }
    const ids = new Set(backups.map((b) => b.id));
    if (aId === null || bId === null || !ids.has(aId) || !ids.has(bId)) {
      setAId(backups[1].id);
      setBId(backups[0].id);
    }
  }, [backups, aId, bId]);

  async function compare() {
    if (aId === null || bId === null) return;
    if (mode === 'decode') return; // DecodeView fetches on its own
    setError(null);
    setUnified('');
    setSideBySide(null);
    try {
      if (mode === 'unified') {
        const response = await api.get('/backups/diff', { params: { a: aId, b: bId }, responseType: 'text' });
        setUnified(response.data as string);
      } else {
        const response = await api.get<SideBySideResponse>('/backups/diff/side-by-side', {
          params: { a: aId, b: bId },
        });
        setSideBySide(response.data);
      }
    } catch (err) {
      setError(humanizeError(err));
    }
  }

  const enoughBackups = backups.length >= 2;
  const labelA = backups.find((b) => b.id === aId);
  const labelB = backups.find((b) => b.id === bId);

  return (
    <main>
      <p className="marker">/06 · DIFF</p>
      <h1 className="headline">Diffs expose drift.</h1>

      <section className="filter-bar">
        <label>
          Switch
          <select value={switchId ?? ''} onChange={(e) => setSwitchId(Number(e.target.value))}>
            {switches.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label>
          Backup A
          <select value={aId ?? ''} disabled={!enoughBackups} onChange={(e) => setAId(Number(e.target.value))}>
            {backups.map((b) => <option key={b.id} value={b.id}>{seqLabel(b)} — {formatTzDateTime(b.created_at)}</option>)}
          </select>
        </label>
        <label>
          Backup B
          <select value={bId ?? ''} disabled={!enoughBackups} onChange={(e) => setBId(Number(e.target.value))}>
            {backups.map((b) => <option key={b.id} value={b.id}>{seqLabel(b)} — {formatTzDateTime(b.created_at)}</option>)}
          </select>
        </label>
        <label>
          View
          <select value={mode} onChange={(e) => setMode(e.target.value as ViewMode)}>
            <option value="side-by-side">Side by side</option>
            <option value="unified">Unified</option>
            <option value="decode">Decode (perubahan config)</option>
          </select>
        </label>
        <button onClick={compare} disabled={!enoughBackups || aId === bId}>
          Compare
        </button>
      </section>

      {!enoughBackups && switchId !== null ? <p>Need at least 2 backups to compare.</p> : null}
      {error ? <div role="alert">{error}</div> : null}

      {mode === 'decode' && aId !== null && bId !== null && aId !== bId ? (
        <DecodeView aId={aId} bId={bId} />
      ) : null}

      {sideBySide ? (
        <section className="diff-side">
          <header className="diff-stats">
            <span className="diff-stat diff-stat-added">+{sideBySide.stats.added_lines} added</span>
            <span className="diff-stat diff-stat-removed">−{sideBySide.stats.removed_lines} removed</span>
            <span className="diff-stat diff-stat-changed">~{sideBySide.stats.changed_lines} changed</span>
          </header>
          <div className="diff-pane-headers">
            <div className="diff-pane-label">A · {labelA ? seqLabel(labelA) : `#${aId}`}{labelA ? ` — ${formatTzDateTime(labelA.created_at)}` : ''}</div>
            <div className="diff-pane-label">B · {labelB ? seqLabel(labelB) : `#${bId}`}{labelB ? ` — ${formatTzDateTime(labelB.created_at)}` : ''}</div>
          </div>
          <div className="diff-grid" role="table" aria-label="Side by side diff">
            {sideBySide.rows.map((row, idx) => (
              <div key={idx} className={`diff-row diff-row-${row.op}`} role="row">
                <span className="diff-line-no" role="cell">{row.line_a > 0 ? row.line_a : ''}</span>
                <pre className="diff-text diff-text-a" role="cell">{row.text_a}</pre>
                <span className="diff-line-no" role="cell">{row.line_b > 0 ? row.line_b : ''}</span>
                <pre className="diff-text diff-text-b" role="cell">{row.text_b}</pre>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {unified ? <pre className="diff-output">{unified}</pre> : null}
    </main>
  );
}
