import { Link, useLocation } from 'wouter';

const groups = [
  { label: 'Monitoring', links: [{ href: '/', text: 'Dashboard' }, { href: '/history', text: 'History' }, { href: '/diff', text: 'Diff' }] },
  { label: 'Management', links: [{ href: '/switches', text: 'Switches' }, { href: '/credentials', text: 'Credentials' }, { href: '/schedules', text: 'Schedules' }] },
  { label: 'Administration', links: [{ href: '/users', text: 'Users' }, { href: '/settings', text: 'Settings' }] },
];

export function Sidebar() {
  const [location] = useLocation();
  return (
    <aside className="sidebar">
      <div className="brand">NCM OPS</div>
      {groups.map((group) => (
        <nav className="nav-group" key={group.label}>
          <div className="nav-label">{group.label}</div>
          {group.links.map((link) => (
            <Link key={link.href} href={link.href} className={`nav-link ${location === link.href ? 'active' : ''}`}>
              {link.text}
            </Link>
          ))}
        </nav>
      ))}
      <div className="marker" style={{ marginTop: 'auto' }}>/REF V4-OPS</div>
    </aside>
  );
}
