import { useEffect, useState } from 'react';
import { fetchBackupContent } from '../api/hooks';

export function BackupViewModal({ backupId, onClose }: { backupId: number; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBackupContent(backupId).then(setText).catch((err) => setError(err.message ?? 'Failed to load'));
  }, [backupId]);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <h2>Backup #{backupId}</h2>
          <button onClick={onClose}>Close</button>
        </header>
        {error ? <p role="alert">{error}</p> : null}
        {text === null && !error ? <p>Loading…</p> : <pre>{text}</pre>}
      </div>
    </div>
  );
}
