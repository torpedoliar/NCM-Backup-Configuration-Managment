import { useState } from 'react';
import { useLogs } from '../../api/hooks';

const LEVELS = ['', 'INFO', 'WARNING', 'ERROR', 'DEBUG'];

export function SettingsLogsSection() {
  const [level, setLevel] = useState('');
  const [q, setQ] = useState('');
  const [lines, setLines] = useState(200);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const { data, refetch } = useLogs({ level: level || undefined, q: q || undefined, lines }, autoRefresh);

  return (
    <section>
      <h2>Logs</h2>
      <div className="filter-bar">
        <label>
          Level
          <select value={level} onChange={(e) => setLevel(e.target.value)}>
            {LEVELS.map((l) => <option key={l} value={l}>{l || 'All'}</option>)}
          </select>
        </label>
        <label>
          Search
          <input value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <button onClick={() => refetch()}>Refresh</button>
        <label>
          <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
          Auto-refresh (5s)
        </label>
      </div>
      <pre className="log-tail">
        {data?.lines.map((line, idx) => (
          <div key={idx} className={`level-${line.level}`}>
            <span className="ts">{line.ts}</span>{' '}
            <span className="level">{line.level}</span>{' '}
            <span className="logger">{line.logger}</span>: {line.message}
          </div>
        ))}
      </pre>
      <footer>
        Showing {data?.total_returned ?? 0} lines · {data?.log_file ?? '—'}
        {' '}
        {data && data.total_returned >= lines && (
          <button onClick={() => setLines(Math.min(5000, lines + 200))}>Load 200 more</button>
        )}
      </footer>
    </section>
  );
}
