import type { ReactNode } from 'react';

export function Drawer({ title, open, children, onClose }: { title: string; open: boolean; children: ReactNode; onClose: () => void }) {
  if (!open) return null;
  return <aside style={{ position: 'fixed', right: 0, top: 0, bottom: 0, width: 420, background: 'var(--surface)', borderLeft: '1px solid var(--amber)', padding: 24 }}><button onClick={onClose}>Close</button><h2>{title}</h2>{children}</aside>;
}
