import { Link, useLocation } from 'wouter';

type NavItem = { href: string; text: string; count?: string; icon: string };
type NavGroup = { label: string; items: NavItem[] };

const groups: NavGroup[] = [
  {
    label: 'Monitoring',
    items: [
      { href: '/', text: 'Dashboard', icon: '▣' },
      { href: '/history', text: 'Backup History', count: '348', icon: '◉' },
      { href: '/diff', text: 'Diff Viewer', icon: '⇆' },
    ],
  },
  {
    label: 'Management',
    items: [
      { href: '/switches', text: 'Switches', count: '12', icon: '▤' },
      { href: '/credentials', text: 'Credentials', count: '8', icon: '⌁' },
      { href: '/schedules', text: 'Schedules', count: '5', icon: '◷' },
    ],
  },
  {
    label: 'Administration',
    items: [
      { href: '/users', text: 'Users', count: '4', icon: '◎' },
      { href: '/settings', text: 'Settings', icon: '⚙' },
    ],
  },
];

export function Sidebar() {
  const [location] = useLocation();
  return (
    <aside className="ops-sidebar">
      <div className="brand-block">
        <div className="brand-title">NCM</div>
        <div className="brand-subtitle">NETWORK CONFIG MGR</div>
        <div className="version-tag"><span className="version-dot" />V3.5.7 / PROD</div>
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
          </nav>
        ))}
      </div>

      <div className="operator-card">
        <span className="operator-avatar">A</span>
        <span>admin</span>
        <span className="operator-online" />
      </div>
    </aside>
  );
}
