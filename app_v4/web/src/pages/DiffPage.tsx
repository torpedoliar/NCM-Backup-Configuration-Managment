import { useState } from 'react';
import { api } from '../api/client';

export function DiffPage() {
  const [left, setLeft] = useState('');
  const [right, setRight] = useState('');
  const [diff, setDiff] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    const a = Number(left);
    const b = Number(right);
    if (!Number.isInteger(a) || !Number.isInteger(b) || a <= 0 || b <= 0) {
      setError('Backup IDs must be positive integers.');
      return;
    }
    try {
      const response = await api.get('/backups/diff', { params: { a, b }, responseType: 'text' });
      setDiff(response.data as string);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load diff');
    }
  }

  return (
    <main>
      <p className="marker">/06 · DIFF</p>
      <h1 className="headline">Diffs expose drift.</h1>
      <input aria-label="left backup" value={left} onChange={(e) => setLeft(e.target.value)} placeholder="Left backup ID" />
      <input aria-label="right backup" value={right} onChange={(e) => setRight(e.target.value)} placeholder="Right backup ID" />
      <button onClick={load}>Compare</button>
      {error ? <div role="alert">{error}</div> : null}
      <pre>{diff}</pre>
    </main>
  );
}
