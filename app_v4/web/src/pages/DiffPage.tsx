import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useFilteredBackups, useSwitches } from '../api/hooks';

export function DiffPage() {
  const { data: switches = [] } = useSwitches();
  const [switchId, setSwitchId] = useState<number | null>(null);
  const { data: backups = [] } = useFilteredBackups(switchId ? { switch_id: switchId } : { switch_id: -1 });
  const [aId, setAId] = useState<number | null>(null);
  const [bId, setBId] = useState<number | null>(null);
  const [diff, setDiff] = useState('');
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
    try {
      const response = await api.get('/backups/diff', { params: { a: aId, b: bId }, responseType: 'text' });
      setDiff(response.data as string);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load diff');
    }
  }

  const enoughBackups = backups.length >= 2;

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
            {backups.map((b) => <option key={b.id} value={b.id}>#{b.id} — {new Date(b.created_at).toLocaleString()}</option>)}
          </select>
        </label>
        <label>
          Backup B
          <select value={bId ?? ''} disabled={!enoughBackups} onChange={(e) => setBId(Number(e.target.value))}>
            {backups.map((b) => <option key={b.id} value={b.id}>#{b.id} — {new Date(b.created_at).toLocaleString()}</option>)}
          </select>
        </label>
        <button onClick={compare} disabled={!enoughBackups || aId === bId}>
          Compare
        </button>
      </section>

      {!enoughBackups && switchId !== null ? <p>Need at least 2 backups to compare.</p> : null}
      {error ? <div role="alert">{error}</div> : null}
      <pre className="diff-output">{diff}</pre>
    </main>
  );
}
