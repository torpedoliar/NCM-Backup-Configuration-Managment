type Tone = 'green' | 'amber' | 'red';

export function StatusPill({ tone = 'green', children }: { tone?: Tone; children: string }) {
  return (
    <span className={`status-pill status-pill-${tone}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}
