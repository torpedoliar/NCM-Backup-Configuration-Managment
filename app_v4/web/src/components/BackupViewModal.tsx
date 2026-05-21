import { useEffect, useState } from 'react';
import { fetchBackupContent } from '../api/hooks';

export function BackupViewModal({ backupId, onClose }: { backupId: number; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchBackupContent(backupId)
      .then((t) => { if (!cancelled) setText(t); })
      .catch((err) => { if (!cancelled) setError(err.message ?? 'Failed to load'); });
    return () => { cancelled = true; };
  }, [backupId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  async function copy() {
    if (text === null) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API may be unavailable; ignore silently.
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <h2>Backup #{backupId}</h2>
          <div className="modal-actions">
            <button onClick={copy} disabled={text === null}>
              {copied ? 'Copied!' : 'Copy'}
            </button>
            <button onClick={onClose}>Close</button>
          </div>
        </header>
        {error ? <p role="alert">{error}</p> : null}
        {text === null && !error ? <p>Loading…</p> : <pre>{text}</pre>}
      </div>
    </div>
  );
}
