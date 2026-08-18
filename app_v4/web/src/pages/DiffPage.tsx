import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useFilteredBackups, useSwitches } from '../api/hooks';
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

type ViewMode = 'side-by-side' | 'unified';

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
            {backups.map((b) => <option key={b.id} value={b.id}>#{b.id} — {formatTzDateTime(b.created_at)}</option>)}
          </select>
        </label>
        <label>
          Backup B
          <select value={bId ?? ''} disabled={!enoughBackups} onChange={(e) => setBId(Number(e.target.value))}>
            {backups.map((b) => <option key={b.id} value={b.id}>#{b.id} — {formatTzDateTime(b.created_at)}</option>)}
          </select>
        </label>
        <label>
          View
          <select value={mode} onChange={(e) => setMode(e.target.value as ViewMode)}>
            <option value="side-by-side">Side by side</option>
            <option value="unified">Unified</option>
          </select>
        </label>
        <button onClick={compare} disabled={!enoughBackups || aId === bId}>
          Compare
        </button>
      </section>

      {!enoughBackups && switchId !== null ? <p>Need at least 2 backups to compare.</p> : null}
      {error ? <div role="alert">{error}</div> : null}

      {sideBySide ? (
        <section className="diff-side">
          <header className="diff-stats">
            <span className="diff-stat diff-stat-added">+{sideBySide.stats.added_lines} added</span>
            <span className="diff-stat diff-stat-removed">−{sideBySide.stats.removed_lines} removed</span>
            <span className="diff-stat diff-stat-changed">~{sideBySide.stats.changed_lines} changed</span>
          </header>
          <div className="diff-pane-headers">
            <div className="diff-pane-label">A · #{aId}{labelA ? ` — ${formatTzDateTime(labelA.created_at)}` : ''}</div>
            <div className="diff-pane-label">B · #{bId}{labelB ? ` — ${formatTzDateTime(labelB.created_at)}` : ''}</div>
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
