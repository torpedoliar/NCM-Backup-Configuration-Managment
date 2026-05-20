import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="ops-shell">
      <Sidebar />
      <section className="ops-main">
        <Topbar />
        <div className="ops-content">{children}</div>
        <footer className="ops-footer">
          <span>NCM // OPS TERMINAL</span>
          <span>Securing your network, one backup at a time.</span>
          <span>SESSION 7C9A · OPERATOR ADMIN</span>
        </footer>
      </section>
    </div>
  );
}
