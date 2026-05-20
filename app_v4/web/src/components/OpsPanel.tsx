import type { ReactNode } from 'react';

export function OpsPanel({
  marker,
  title,
  children,
  className = '',
}: {
  marker: string;
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`ops-panel ${className}`}>
      <div className="panel-marker">{marker}</div>
      {title ? <h2 className="panel-title">{title}</h2> : null}
      {children}
    </section>
  );
}
