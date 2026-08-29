import { Link, useLocation } from 'wouter';
import { useSystemMetrics } from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';

type NavItem = { href: string; text: string; count?: string; icon: string };
type NavGroup = { label: string; items: NavItem[] };

const count = (n?: number) => (n === undefined ? '—' : String(n));

export function Sidebar() {
  const [location] = useLocation();
  const { data: metrics } = useSystemMetrics();
  const auth = useAuth();
  const role = auth.user?.role;

  const groups: NavGroup[] = [
    {
      label: 'Monitoring',
      items: [
        { href: '/', text: 'Dashboard', icon: '▣' },
        { href: '/history', text: 'Backup History', count: count(metrics?.backups), icon: '◉' },
        { href: '/diff', text: 'Diff Viewer', icon: '⇆' },
        { href: '/decode', text: 'Decode', icon: '⌗' },
      ],
    },
    {
      label: 'Management',
      items: [
        { href: '/switches', text: 'Switches', count: count(metrics?.switches), icon: '▤' },
        ...(role === 'viewer'
          ? []
          : [{ href: '/credentials', text: 'Credentials', icon: '⌁' }]),
        { href: '/schedules', text: 'Schedules', count: count(metrics?.jobs), icon: '◷' },
        ...(role === 'viewer'
          ? []
          : [
              { href: '/config-review', text: 'Config Review', count: count(metrics?.pending_reviews), icon: '⚠' },
              { href: '/baselines', text: 'Baselines', icon: '☰' },
            ]),
      ],
    },
    {
      label: 'Administration',
      items: [
        ...(role === 'viewer'
          ? []
          : [{ href: '/users', text: 'Users', count: count(undefined), icon: '◎' }]),
        { href: '/settings', text: 'Settings', icon: '⚙' },
      ],
    },
  ];

  return (
    <aside className="ops-sidebar">
      <div className="brand-block">
        <div className="brand-title">NCM</div>
        <div className="brand-subtitle">NETWORK CONFIG MGR</div>
        <div className="version-tag"><span className="version-dot" />V4.6.0 / PROD</div>
      </div>

      <div className="nav-sections">
        {groups.map((group) => (
          <nav className="nav-section" key={group.label} aria-label={group.label}>
            <div className="nav-section-title">
              <span>{group.label.toUpperCase()}</span>
            </div>
            {group.items.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-item ${location === item.href ? 'active' : ''}`}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.text}</span>
                {item.count ? <span className="nav-count">{item.count}</span> : null}
              </Link>
            ))}
            {group.label === 'Monitoring' && role === 'admin' ? (
              <Link
                href="/audit"
                className={`nav-item ${location === '/audit' ? 'active' : ''}`}
              >
                <span className="nav-icon">⏱</span>
                <span>Activity</span>
              </Link>
            ) : null}
          </nav>
        ))}
      </div>

      <footer className="sidebar-footer">
        <span className="user-chip">
          <span className="dot ok" /> {auth.user?.username ?? 'admin'}
        </span>
        <button type="button" className="sign-out" onClick={() => { void auth.logout(); }}>
          Sign out ↗
        </button>
      </footer>
    </aside>
  );
}
