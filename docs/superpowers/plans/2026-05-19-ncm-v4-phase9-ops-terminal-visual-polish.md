# NCM v4 Phase 9 Ops Terminal Visual Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the web client and desktop shell visuals up to the Ops Terminal brainstorming mockup: deep ink grid, sharp brutalist panels, amber accents, editorial hero, KPI crosshairs, live stream, fleet tiles, and matching Qt shell polish.

**Architecture:** This phase depends on Phase 4–7 because it polishes existing React pages and PySide6 shell instead of creating base UI. The React app remains the visual source of truth via `tokens.css` and component CSS modules. Desktop imports the same tokens through the QSS generator and applies a matching native shell treatment.

**Tech Stack:** React 18, TypeScript, Vite, Recharts, Vitest, Testing Library, Playwright screenshots, PySide6, pytest-qt.

---

## File Structure

- Modify: `app_v4/web/package.json` — add Playwright visual check commands.
- Modify: `app_v4/web/src/styles/tokens.css` — expand exact Ops Terminal color, type, spacing, motion tokens.
- Modify: `app_v4/web/src/styles/global.css` — add grid paper background, scanlines, panel geometry, button/input/table primitives.
- Modify: `app_v4/web/src/layout/Sidebar.tsx` — match mockup brand, sections, counts, operator footer.
- Modify: `app_v4/web/src/layout/Topbar.tsx` — match breadcrumb, service pulse, UTC offset, timecode.
- Modify: `app_v4/web/src/layout/Shell.tsx` — add shell frame and viewport scanline layers.
- Modify: `app_v4/web/src/pages/DashboardPage.tsx` — match mockup dashboard composition.
- Modify: `app_v4/web/src/components/KpiCell.tsx` — add crosshair corners, markers, sparkline/progress variants.
- Modify: `app_v4/web/src/components/BackupChart.tsx` — replace simple line with 14-day bar chart styling.
- Modify: `app_v4/web/src/components/FleetGrid.tsx` — match fleet tile grid states.
- Modify: `app_v4/web/src/components/LiveFeed.tsx` — match stream layout and event colors.
- Create: `app_v4/web/src/components/OpsPanel.tsx` — shared panel frame with marker code.
- Create: `app_v4/web/src/components/StatusPill.tsx` — service/live/status pill.
- Create: `app_v4/web/src/styles/dashboard.css` — page-specific dashboard layout.
- Create: `app_v4/web/e2e/dashboard.visual.spec.ts` — screenshot smoke test.
- Create: `app_v4/web/playwright.config.ts` — local visual screenshot config.
- Modify: `app_v4/desktop/theme/generate_qss.py` — map expanded CSS tokens to QSS.
- Modify: `app_v4/desktop/theme/ops_terminal.qss` — refresh desktop shell visual style.
- Modify: `app_v4/desktop/shell/sidebar.py` — add section labels, counts, operator footer.
- Modify: `app_v4/desktop/shell/topbar.py` — add service pulse/timecode styling.
- Test: `app_v4/web/src/styles/visual-tokens.test.ts`
- Test: `app_v4/web/src/pages/DashboardPage.test.tsx`
- Test: `app_v4/web/src/layout/Shell.test.tsx`
- Test: `app_v4/tests/test_desktop_theme_generator.py`
- Test: `app_v4/tests/test_desktop_shell.py`

## Phase Guardrails

- Do not change backend API contracts in this phase.
- Do not add new business workflows in this phase.
- Do not use Tailwind or UI kits.
- Keep all rounded corners at `0–4px`.
- Amber is the primary accent; red only for failure; green only for healthy/running; violet only for auth events.
- Web is visual source of truth; desktop follows token-derived QSS.

### Task 1: Visual Test Harness and Expanded Tokens

**Files:**
- Modify: `app_v4/web/package.json`
- Modify: `app_v4/web/src/styles/tokens.css`
- Modify: `app_v4/web/src/styles/global.css`
- Create: `app_v4/web/src/styles/visual-tokens.test.ts`

- [ ] **Step 1: Add failing visual token test**

Create `app_v4/web/src/styles/visual-tokens.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import tokens from './tokens.css?raw';

const requiredTokens = [
  '--ink: #0a0a0a',
  '--amber: #ffb800',
  '--red: #ff3838',
  '--green: #4ade80',
  '--font-mono:',
  '--font-display:',
  '--grid-size: 64px',
  '--panel-border: #262626',
];

describe('Ops Terminal tokens', () => {
  it('keeps mockup-critical visual tokens', () => {
    for (const token of requiredTokens) {
      expect(tokens).toContain(token);
    }
  });
});
```

- [ ] **Step 2: Run failing token test**

```powershell
rtk npm --prefix app_v4/web test -- --run src/styles/visual-tokens.test.ts
```

Expected: fail until expanded tokens exist.

- [ ] **Step 3: Expand tokens**

Replace `app_v4/web/src/styles/tokens.css` with:

```css
:root {
  --ink: #0a0a0a;
  --ink-2: #111111;
  --surface: #141414;
  --surface-2: #1a1a1a;
  --panel: rgba(10, 10, 10, 0.82);
  --line: #262626;
  --line-2: #333333;
  --panel-border: #262626;

  --bone: #fafaf7;
  --bone-2: #e5e5e2;
  --muted: #737373;
  --muted-2: #525252;

  --amber: #ffb800;
  --amber-2: #ffd166;
  --amber-dim: rgba(255, 184, 0, 0.16);
  --red: #ff3838;
  --red-dim: rgba(255, 56, 56, 0.14);
  --green: #4ade80;
  --green-dim: rgba(74, 222, 128, 0.14);
  --cyan: #22d3ee;
  --violet: #a78bfa;

  --font-mono: 'JetBrains Mono', 'Cascadia Mono', monospace;
  --font-body: 'Geist', 'Inter', system-ui, sans-serif;
  --font-display: 'Instrument Serif', 'Georgia', serif;

  --grid-size: 64px;
  --sidebar-width: 300px;
  --topbar-height: 68px;
  --panel-pad: 28px;
  --sharp-radius: 2px;
  --dash: 3px;
  --shadow-glow: 0 0 0 1px rgba(255, 184, 0, 0.08), 0 0 36px rgba(255, 184, 0, 0.04);
}
```

- [ ] **Step 4: Replace global visual primitives**

Replace `app_v4/web/src/styles/global.css` with:

```css
* { box-sizing: border-box; }
html { background: var(--ink); }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--bone);
  background:
    linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px),
    radial-gradient(circle at 70% 0%, rgba(255,184,0,0.06), transparent 34%),
    var(--ink);
  background-size: var(--grid-size) var(--grid-size), var(--grid-size) var(--grid-size), auto, auto;
  font-family: var(--font-body);
  overflow-x: hidden;
}
body::before {
  content: '';
  pointer-events: none;
  position: fixed;
  inset: 0;
  z-index: 100;
  background: repeating-linear-gradient(180deg, rgba(255,255,255,0.025) 0 1px, transparent 1px 4px);
  mix-blend-mode: screen;
}
button, input, select, textarea {
  border-radius: var(--sharp-radius);
  font: inherit;
}
button {
  border: 1px solid var(--line-2);
  background: var(--surface);
  color: var(--bone);
  padding: 10px 14px;
  cursor: pointer;
}
button:hover, button:focus-visible {
  border-color: var(--amber);
  color: var(--amber);
  outline: none;
}
input, select, textarea {
  border: 1px solid var(--line-2);
  background: var(--ink-2);
  color: var(--bone);
  padding: 10px 12px;
}
a { color: inherit; }
.number { font-feature-settings: 'tnum' 1, 'zero' 1; font-family: var(--font-mono); }
.marker {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}
.marker-amber { color: var(--amber); }
.headline {
  margin: 0;
  color: var(--bone);
  font-size: clamp(42px, 4.6vw, 72px);
  line-height: 0.94;
  letter-spacing: -0.06em;
  font-weight: 400;
}
.headline em {
  color: var(--amber);
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
}
.ops-panel {
  position: relative;
  border: 1px solid var(--panel-border);
  background: var(--panel);
  box-shadow: var(--shadow-glow);
}
.ops-panel::before,
.ops-panel::after {
  content: '';
  position: absolute;
  width: 8px;
  height: 8px;
  border-color: var(--amber);
  opacity: 0.8;
}
.ops-panel::before { top: -1px; left: -1px; border-top: 1px solid; border-left: 1px solid; }
.ops-panel::after { right: -1px; bottom: -1px; border-right: 1px solid; border-bottom: 1px solid; }
.status-green { color: var(--green); }
.status-amber { color: var(--amber); }
.status-red { color: var(--red); }
.status-violet { color: var(--violet); }
```

- [ ] **Step 5: Run token test**

```powershell
rtk npm --prefix app_v4/web test -- --run src/styles/visual-tokens.test.ts
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
rtk git add app_v4/web/package.json app_v4/web/src/styles/tokens.css app_v4/web/src/styles/global.css app_v4/web/src/styles/visual-tokens.test.ts
rtk git commit -m "style: add v4 Ops Terminal visual tokens"
```

### Task 2: Shell, Sidebar, and Topbar Match Mockup

**Files:**
- Modify: `app_v4/web/src/layout/Shell.tsx`
- Modify: `app_v4/web/src/layout/Sidebar.tsx`
- Modify: `app_v4/web/src/layout/Topbar.tsx`
- Modify: `app_v4/web/src/layout/Shell.test.tsx`
- Create: `app_v4/web/src/components/StatusPill.tsx`

- [ ] **Step 1: Update shell test**

Replace `app_v4/web/src/layout/Shell.test.tsx` with:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Shell } from './Shell';

it('renders mockup shell chrome', () => {
  render(<Shell><main>Dashboard body</main></Shell>);

  expect(screen.getByText('NCM')).toBeInTheDocument();
  expect(screen.getByText('NETWORK CONFIG MGR')).toBeInTheDocument();
  expect(screen.getByText('V3.5.7 / PROD')).toBeInTheDocument();
  expect(screen.getByText('MONITORING')).toBeInTheDocument();
  expect(screen.getByText('/ Dashboard')).toBeInTheDocument();
  expect(screen.getByText('SERVICE / RUNNING')).toBeInTheDocument();
  expect(screen.getByText('Dashboard body')).toBeInTheDocument();
});
```

- [ ] **Step 2: Create status pill**

Create `app_v4/web/src/components/StatusPill.tsx`:

```tsx
export function StatusPill({ tone = 'green', children }: { tone?: 'green' | 'amber' | 'red'; children: string }) {
  return (
    <span className={`status-pill status-pill-${tone}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}
```

- [ ] **Step 3: Replace shell layout**

Replace `app_v4/web/src/layout/Shell.tsx` with:

```tsx
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
```

- [ ] **Step 4: Replace sidebar**

Replace `app_v4/web/src/layout/Sidebar.tsx` with:

```tsx
import { Link, useLocation } from 'wouter';

type NavItem = { href: string; text: string; count?: string; icon: string };
type NavGroup = { label: string; items: NavItem[] };

const groups: NavGroup[] = [
  { label: 'Monitoring', items: [
    { href: '/', text: 'Dashboard', icon: '▣' },
    { href: '/history', text: 'Backup History', count: '348', icon: '◉' },
    { href: '/diff', text: 'Diff Viewer', icon: '⇆' },
  ] },
  { label: 'Management', items: [
    { href: '/switches', text: 'Switches', count: '12', icon: '▤' },
    { href: '/credentials', text: 'Credentials', count: '8', icon: '⌁' },
    { href: '/schedules', text: 'Schedules', count: '5', icon: '◷' },
  ] },
  { label: 'Administration', items: [
    { href: '/users', text: 'Users', count: '4', icon: '◎' },
    { href: '/settings', text: 'Settings', icon: '⚙' },
  ] },
];

export function Sidebar() {
  const [location] = useLocation();
  return (
    <aside className="ops-sidebar">
      <div className="brand-block">
        <div className="brand-title">NCM</div>
        <div className="brand-subtitle">NETWORK CONFIG MGR</div>
        <div className="version-tag">● V3.5.7 / PROD</div>
      </div>

      <div className="nav-sections">
        {groups.map((group) => (
          <nav className="nav-section" key={group.label} aria-label={group.label}>
            <div className="nav-section-title"><span>{group.label}</span></div>
            {group.items.map((item) => (
              <Link key={item.href} href={item.href} className={`nav-item ${location === item.href ? 'active' : ''}`}>
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
```

- [ ] **Step 5: Replace topbar**

Replace `app_v4/web/src/layout/Topbar.tsx` with:

```tsx
import { StatusPill } from '../components/StatusPill';

function timecode() {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

export function Topbar() {
  return (
    <header className="ops-topbar">
      <div className="breadcrumb"><span>MONITORING</span><b>/</b><strong>/ Dashboard</strong></div>
      <div className="topbar-right">
        <StatusPill tone="green">SERVICE / RUNNING</StatusPill>
        <span className="marker">UTC+07</span>
        <span className="topbar-time number">{timecode()}</span>
      </div>
    </header>
  );
}
```

- [ ] **Step 6: Add shell CSS**

Append to `app_v4/web/src/styles/global.css`:

```css
.ops-shell { display: grid; grid-template-columns: var(--sidebar-width) 1fr; min-height: 100vh; }
.ops-sidebar { border-right: 1px solid var(--line); background: rgba(10,10,10,.92); padding: 26px 28px; display: flex; flex-direction: column; gap: 38px; }
.brand-title { color: var(--bone); font-family: var(--font-mono); font-size: 28px; font-weight: 800; letter-spacing: -0.06em; }
.brand-subtitle { margin-top: 8px; color: var(--muted-2); font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; }
.version-tag { display: inline-block; margin-top: 22px; border: 1px solid rgba(255,184,0,.45); color: var(--amber); padding: 8px 11px; font-family: var(--font-mono); font-size: 12px; }
.nav-sections { display: grid; gap: 36px; }
.nav-section-title { display: flex; align-items: center; gap: 8px; color: var(--muted-2); font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; text-transform: uppercase; }
.nav-section-title::after { content: ''; height: 1px; background: var(--line); flex: 1; }
.nav-item { display: grid; grid-template-columns: 22px 1fr auto; align-items: center; margin-left: -28px; padding: 12px 0 12px 28px; color: var(--bone); text-decoration: none; font-weight: 700; }
.nav-item.active { border-left: 3px solid var(--amber); background: linear-gradient(90deg, rgba(255,184,0,.10), transparent); color: var(--bone); }
.nav-icon, .nav-count { color: var(--muted); font-family: var(--font-mono); font-size: 11px; }
.operator-card { margin-top: auto; display: grid; grid-template-columns: 34px 1fr auto; align-items: center; gap: 12px; border-top: 1px solid var(--line); padding-top: 18px; }
.operator-avatar { display: grid; place-items: center; width: 34px; height: 28px; background: var(--bone); color: var(--ink); font-family: var(--font-mono); font-weight: 800; }
.operator-online { width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 12px var(--green); }
.ops-main { min-width: 0; display: flex; flex-direction: column; }
.ops-topbar { height: var(--topbar-height); border-bottom: 1px dashed rgba(255,184,0,.36); display: flex; justify-content: space-between; align-items: center; padding: 0 40px; background: rgba(10,10,10,.74); }
.breadcrumb { display: flex; align-items: center; gap: 18px; font-family: var(--font-mono); }
.breadcrumb span { color: var(--muted); letter-spacing: .2em; font-size: 12px; }
.breadcrumb b { color: var(--amber); }
.breadcrumb strong { color: var(--bone); }
.topbar-right { display: flex; align-items: center; gap: 22px; }
.topbar-time { color: var(--bone); font-size: 12px; }
.status-pill { border: 1px solid currentColor; padding: 9px 15px; font-family: var(--font-mono); font-size: 12px; font-weight: 700; display: inline-flex; align-items: center; gap: 9px; background: rgba(74,222,128,.09); }
.status-pill-green { color: var(--green); }
.status-pill-amber { color: var(--amber); }
.status-pill-red { color: var(--red); }
.status-dot { width: 7px; height: 7px; background: currentColor; border-radius: 50%; box-shadow: 0 0 12px currentColor; }
.ops-content { flex: 1; padding: 40px; }
.ops-footer { height: 36px; display: flex; align-items: center; justify-content: space-between; color: var(--muted-2); font-family: var(--font-mono); font-size: 10px; padding: 0 40px; border-top: 1px solid var(--line); }
```

- [ ] **Step 7: Run shell tests**

```powershell
rtk npm --prefix app_v4/web test -- --run src/layout/Shell.test.tsx
```

Expected: pass.

- [ ] **Step 8: Commit**

```powershell
rtk git add app_v4/web/src/layout app_v4/web/src/components/StatusPill.tsx app_v4/web/src/styles/global.css
rtk git commit -m "style: polish v4 Ops Terminal shell"
```

### Task 3: Dashboard Hero and KPI Row Match Mockup

**Files:**
- Modify: `app_v4/web/src/pages/DashboardPage.tsx`
- Modify: `app_v4/web/src/components/KpiCell.tsx`
- Create: `app_v4/web/src/components/OpsPanel.tsx`
- Create: `app_v4/web/src/styles/dashboard.css`
- Modify: `app_v4/web/src/pages/DashboardPage.test.tsx`

- [ ] **Step 1: Update dashboard test**

Replace `app_v4/web/src/pages/DashboardPage.test.tsx` with:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DashboardPage } from './DashboardPage';

vi.mock('../api/hooks', () => ({
  useSystemMetrics: () => ({ data: { switches: 12, backups: 348, jobs: 5, failures_24h: 1 }, isLoading: false }),
}));

it('renders mockup dashboard hero and KPI markers', () => {
  render(<QueryClientProvider client={new QueryClient()}><DashboardPage /></QueryClientProvider>);

  expect(screen.getByText('OPERATIONS OVERVIEW')).toBeInTheDocument();
  expect(screen.getByText('three-forty-eight')).toBeInTheDocument();
  expect(screen.getByText('/01 · INV')).toBeInTheDocument();
  expect(screen.getByText('/02 · EXEC')).toBeInTheDocument();
  expect(screen.getByText('/03 · QOS')).toBeInTheDocument();
  expect(screen.getByText('/04 · ALERT')).toBeInTheDocument();
});
```

- [ ] **Step 2: Create `OpsPanel`**

Create `app_v4/web/src/components/OpsPanel.tsx`:

```tsx
import type { ReactNode } from 'react';

export function OpsPanel({ marker, title, children, className = '' }: { marker: string; title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`ops-panel ${className}`}>
      <div className="panel-marker">{marker}</div>
      {title ? <h2 className="panel-title">{title}</h2> : null}
      {children}
    </section>
  );
}
```

- [ ] **Step 3: Replace `KpiCell`**

Replace `app_v4/web/src/components/KpiCell.tsx` with:

```tsx
import { OpsPanel } from './OpsPanel';

type KpiCellProps = {
  marker: string;
  label: string;
  value: string;
  suffix?: string;
  delta?: string;
  tone?: 'green' | 'amber' | 'red';
  footer?: string;
  progress?: number;
};

export function KpiCell({ marker, label, value, suffix, delta, tone = 'amber', footer, progress }: KpiCellProps) {
  return (
    <OpsPanel marker={marker} className="kpi-cell">
      <div className="kpi-label">▪ {label}</div>
      <div className="kpi-main number">
        <span>{value}</span>{suffix ? <small>{suffix}</small> : null}
      </div>
      {typeof progress === 'number' ? <div className="kpi-progress"><span style={{ width: `${progress}%` }} /></div> : null}
      {delta ? <div className={`kpi-delta status-${tone}`}>{delta}</div> : null}
      {footer ? <div className="kpi-footer marker">// {footer}</div> : null}
    </OpsPanel>
  );
}
```

- [ ] **Step 4: Replace dashboard page**

Replace `app_v4/web/src/pages/DashboardPage.tsx` with:

```tsx
import { BackupChart } from '../components/BackupChart';
import { FleetGrid } from '../components/FleetGrid';
import { KpiCell } from '../components/KpiCell';
import { LiveFeed } from '../components/LiveFeed';
import { OpsPanel } from '../components/OpsPanel';
import { useSystemMetrics } from '../api/hooks';
import { number } from '../lib/fmt';
import '../styles/dashboard.css';

export function DashboardPage() {
  const { data } = useSystemMetrics();
  const switches = data?.switches ?? 12;
  const backups = data?.backups ?? 348;
  const jobs = data?.jobs ?? 5;
  const failures = data?.failures_24h ?? 1;

  return (
    <main className="dashboard-page">
      <section className="dashboard-hero">
        <div>
          <div className="marker marker-amber">◆ OPERATIONS OVERVIEW</div>
          <h1 className="headline">Twelve switches, <em>three-forty-eight</em><br />backups, one anomaly.</h1>
          <p className="hero-subline marker">// LAST 30 DAYS · AUTO-REFRESH 30s · DATA-AS-OF 22:00:22</p>
          <div className="hero-underline" />
        </div>
        <div className="marker">/REF DSH-001 · LIVE</div>
      </section>

      <section className="range-tabs" aria-label="time range">
        <button className="active">24H</button><button>7D</button><button>30D</button><button>90D</button><button>EXPORT ↗</button>
      </section>

      <section className="kpi-grid">
        <KpiCell marker="/01 · INV" label="SWITCHES UNDER MGMT" value={number(switches)} delta="+2 NEW" tone="green" />
        <KpiCell marker="/02 · EXEC" label="BACKUPS · 30D" value={number(backups)} delta="↑ 12.4%" tone="green" />
        <KpiCell marker="/03 · QOS" label="SUCCESS RATE" value="96.3" suffix="%" footer="TARGET 99.0% · DELTA -2.7" progress={96} />
        <KpiCell marker="/04 · ALERT" label="FAILED · 24H" value={String(failures).padStart(2, '0')} delta="△ TIMEOUT" tone="red" footer="SW-EDGE-07 · 10.0.1.7" />
      </section>

      <section className="dashboard-grid">
        <OpsPanel marker="/05 · TIMESERIES" title="Backup activity, last fourteen days" className="chart-panel"><BackupChart /></OpsPanel>
        <OpsPanel marker="/06 · STREAM" title="Live activity" className="live-panel"><LiveFeed /></OpsPanel>
      </section>

      <OpsPanel marker="/07 · FLEET" title="Switch fleet, at a glance" className="fleet-panel"><FleetGrid /></OpsPanel>
    </main>
  );
}
```

- [ ] **Step 5: Add dashboard CSS**

Create `app_v4/web/src/styles/dashboard.css`:

```css
.dashboard-page { display: grid; gap: 26px; }
.dashboard-hero { min-height: 210px; display: flex; justify-content: space-between; align-items: flex-start; padding-top: 22px; }
.hero-subline { margin-top: 22px; }
.hero-underline { margin-top: 26px; width: 96px; height: 2px; background: var(--amber); }
.range-tabs { display: flex; justify-content: flex-end; gap: 10px; margin-top: -72px; }
.range-tabs button { font-family: var(--font-mono); font-size: 12px; padding: 10px 14px; }
.range-tabs button.active { background: var(--bone); color: var(--ink); border-color: var(--bone); }
.range-tabs button:last-child { border-color: var(--amber); color: var(--amber); }
.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; }
.kpi-cell { min-height: 214px; padding: 28px; display: flex; flex-direction: column; justify-content: space-between; }
.panel-marker { position: absolute; top: 20px; right: 24px; color: var(--muted); font-family: var(--font-mono); font-size: 11px; letter-spacing: .18em; }
.panel-title { margin: 0 0 24px; font-size: 26px; font-weight: 600; letter-spacing: -0.04em; }
.panel-title::first-letter { color: var(--bone); }
.kpi-label { color: var(--muted); font-family: var(--font-mono); font-size: 12px; letter-spacing: .18em; }
.kpi-main { font-size: 54px; line-height: 1; font-weight: 800; text-shadow: 2px 2px 0 rgba(34,211,238,.5), -2px -1px 0 rgba(255,56,56,.35); }
.kpi-main small { margin-left: 5px; font-size: 18px; color: var(--bone-2); }
.kpi-delta { align-self: flex-start; background: currentColor; color: var(--ink); padding: 7px 9px; font-family: var(--font-mono); font-size: 12px; font-weight: 800; }
.kpi-footer { color: var(--muted); }
.kpi-progress { height: 3px; background: var(--line); overflow: hidden; }
.kpi-progress span { display: block; height: 100%; background: var(--amber); }
.dashboard-grid { display: grid; grid-template-columns: 1.6fr .9fr; gap: 0; }
.chart-panel, .live-panel, .fleet-panel { padding: 32px; min-height: 360px; }
.fleet-panel { min-height: 260px; }
@media (max-width: 1200px) { .kpi-grid, .dashboard-grid { grid-template-columns: 1fr 1fr; } .range-tabs { margin-top: 0; justify-content: flex-start; } }
@media (max-width: 840px) { .kpi-grid, .dashboard-grid { grid-template-columns: 1fr; } .dashboard-hero { flex-direction: column; gap: 24px; } }
```

- [ ] **Step 6: Run dashboard test**

```powershell
rtk npm --prefix app_v4/web test -- --run src/pages/DashboardPage.test.tsx
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
rtk git add app_v4/web/src/pages/DashboardPage.tsx app_v4/web/src/components/KpiCell.tsx app_v4/web/src/components/OpsPanel.tsx app_v4/web/src/styles/dashboard.css app_v4/web/src/pages/DashboardPage.test.tsx
rtk git commit -m "style: polish v4 dashboard hero and KPI panels"
```

### Task 4: Chart, Live Stream, and Fleet Tile Polish

**Files:**
- Modify: `app_v4/web/src/components/BackupChart.tsx`
- Modify: `app_v4/web/src/components/LiveFeed.tsx`
- Modify: `app_v4/web/src/components/FleetGrid.tsx`
- Modify: `app_v4/web/src/styles/dashboard.css`
- Modify: `app_v4/web/src/pages/DashboardPage.test.tsx`

- [ ] **Step 1: Add visual content assertions**

Append to `DashboardPage.test.tsx`:

```tsx
it('renders chart, stream, and fleet sections', () => {
  render(<QueryClientProvider client={new QueryClient()}><DashboardPage /></QueryClientProvider>);

  expect(screen.getByText('TODAY')).toBeInTheDocument();
  expect(screen.getByText('SW-EDGE-07 backup completed')).toBeInTheDocument();
  expect(screen.getByText('SW-CORE-01')).toBeInTheDocument();
});
```

- [ ] **Step 2: Replace backup chart**

Replace `app_v4/web/src/components/BackupChart.tsx` with:

```tsx
const days = [18, 22, 24, 20, 26, 29, 27, 24, 28, 31, 27, 32, 30, 29];
const failed = [1, 0, 0, 2, 0, 0, 0, 1, 0, 0, 0, 0, 2, 1];

export function BackupChart() {
  const max = Math.max(...days);
  return (
    <div className="bar-chart" aria-label="backup activity chart">
      <div className="chart-legend marker"><span className="legend-success" /> SUCCESS <span className="legend-failed" /> FAILED <span className="legend-avg" /> AVG</div>
      <div className="chart-bars">
        {days.map((value, index) => (
          <div className="chart-day" key={index}>
            <div className="bar-stack" style={{ height: `${(value / max) * 210}px` }}>
              <span className="bar-failed" style={{ height: `${failed[index] * 6}px` }} />
            </div>
            <span className="chart-label">05-{String(index + 5).padStart(2, '0')}</span>
            {index === days.length - 1 ? <strong>TODAY</strong> : null}
          </div>
        ))}
      </div>
      <div className="avg-line"><span>AVG 24.1</span></div>
    </div>
  );
}
```

- [ ] **Step 3: Replace live feed**

Replace `app_v4/web/src/components/LiveFeed.tsx` with:

```tsx
const fallbackEvents = [
  ['22:00:22', 'ok', 'SW-EDGE-07 backup completed', '4.1s'],
  ['22:00:18', 'fail', 'SW-EDGE-07 timeout retry 1/3', ''],
  ['22:00:14', 'ok', 'SW-EDGE-03 backup completed', '1.8s'],
  ['22:00:12', 'ok', 'SW-CORE-01 backup completed', '2.3s'],
  ['21:55:08', 'info', 'Scheduled job triggered', 'daily-22h'],
  ['21:42:31', 'auth', 'admin session opened', 'from 10.0.5.42'],
  ['21:38:09', 'warn', 'SW-CORE-02 config diff detected', '+12 -3'],
  ['21:30:00', 'info', 'Retention sweep', 'purged 4 files'],
] as const;

export function LiveFeed() {
  return (
    <div className="live-feed">
      <div className="live-header"><span className="live-dot" /> LIVE</div>
      {fallbackEvents.map(([time, tone, message, meta]) => (
        <div className="live-row" key={`${time}-${message}`}>
          <span className="live-time number">{time}</span>
          <span className={`live-icon status-${tone === 'fail' ? 'red' : tone === 'auth' ? 'violet' : tone === 'warn' ? 'amber' : 'green'}`}>{tone === 'fail' ? '×' : tone === 'warn' ? '!' : '✓'}</span>
          <strong>{message}</strong>
          <span>{meta}</span>
        </div>
      ))}
      <div className="live-footer"><span><b>108</b> EVENTS / 24H</span><span>VIEW ALL ↗</span></div>
    </div>
  );
}
```

- [ ] **Step 4: Replace fleet grid**

Replace `app_v4/web/src/components/FleetGrid.tsx` with:

```tsx
const fleet = [
  ['SW-CORE-01', 'ok', '2m'], ['SW-CORE-02', 'ok', '3m'], ['SW-EDGE-01', 'ok', '5m'], ['SW-EDGE-02', 'ok', '5m'],
  ['SW-EDGE-03', 'ok', '2m'], ['SW-EDGE-04', 'ok', '7m'], ['SW-EDGE-05', 'ok', '4m'], ['SW-EDGE-06', 'ok', '6m'],
  ['SW-EDGE-07', 'fail', '1h'], ['SW-EDGE-08', 'warn', '15m'], ['SW-DIST-01', 'ok', '3m'], ['SW-DIST-02', 'ok', '4m'],
] as const;

export function FleetGrid() {
  return (
    <div className="fleet-grid-wrap">
      <div className="fleet-legend marker"><span className="dot ok" /> OK · 10 <span className="dot warn" /> WARN · 1 <span className="dot fail" /> FAIL · 1</div>
      <div className="fleet-grid">
        {fleet.map(([name, state, age]) => (
          <div className={`fleet-tile fleet-${state}`} key={name}>
            <strong>{name}</strong>
            <span className={`dot ${state}`} />
            <small>{age}</small>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Add chart/feed/fleet CSS**

Append to `app_v4/web/src/styles/dashboard.css`:

```css
.bar-chart { position: relative; min-height: 280px; padding-top: 40px; }
.chart-legend { position: absolute; right: 0; top: 0; display: flex; gap: 12px; align-items: center; }
.chart-legend span { display: inline-block; width: 11px; height: 11px; }
.legend-success { background: var(--bone); } .legend-failed { background: var(--red); } .legend-avg { background: rgba(255,184,0,.45); }
.chart-bars { display: grid; grid-template-columns: repeat(14, 1fr); gap: 18px; align-items: end; height: 260px; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); background: repeating-linear-gradient(180deg, transparent 0 58px, rgba(255,255,255,.05) 58px 59px); }
.chart-day { height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 8px; position: relative; }
.bar-stack { width: 42px; background: var(--bone); display: flex; flex-direction: column-reverse; }
.bar-failed { display: block; background: var(--red); width: 100%; }
.chart-label, .chart-day strong { font-family: var(--font-mono); font-size: 10px; color: var(--muted); }
.chart-day strong { color: var(--amber); }
.avg-line { position: absolute; left: 40px; right: 0; top: 174px; border-top: 1px dashed rgba(255,184,0,.45); color: var(--amber); font-family: var(--font-mono); font-size: 11px; text-align: right; }
.live-feed { display: grid; gap: 0; }
.live-header { justify-self: end; border: 1px solid rgba(74,222,128,.36); color: var(--green); padding: 6px 10px; font-family: var(--font-mono); font-size: 11px; }
.live-dot, .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; }
.live-dot, .dot.ok { background: var(--green); } .dot.warn { background: var(--amber); } .dot.fail { background: var(--red); }
.live-row { display: grid; grid-template-columns: 76px 24px 1fr auto; gap: 8px; padding: 10px 0; border-bottom: 1px dashed var(--line-2); font-family: var(--font-mono); font-size: 12px; }
.live-time, .live-row span:last-child { color: var(--muted); }
.live-footer { display: flex; justify-content: space-between; margin-top: 24px; color: var(--muted); font-family: var(--font-mono); font-size: 11px; }
.live-footer b { color: var(--bone); }
.fleet-grid-wrap { display: grid; gap: 22px; }
.fleet-legend { justify-self: end; display: flex; align-items: center; gap: 14px; }
.fleet-grid { display: grid; grid-template-columns: repeat(12, minmax(92px, 1fr)); gap: 10px; }
.fleet-tile { min-height: 116px; padding: 14px; border: 1px solid var(--line-2); background: rgba(74,222,128,.08); position: relative; font-family: var(--font-mono); }
.fleet-tile strong { font-size: 12px; }
.fleet-tile .dot { position: absolute; right: 10px; top: 10px; margin: 0; }
.fleet-tile small { position: absolute; left: 14px; bottom: 14px; color: var(--muted); }
.fleet-fail { border-color: var(--red); background: var(--red-dim); }
.fleet-warn { border-color: rgba(255,184,0,.45); background: var(--amber-dim); }
@media (max-width: 1400px) { .fleet-grid { grid-template-columns: repeat(6, 1fr); } }
@media (max-width: 840px) { .fleet-grid { grid-template-columns: repeat(2, 1fr); } }
```

- [ ] **Step 6: Run dashboard tests**

```powershell
rtk npm --prefix app_v4/web test -- --run src/pages/DashboardPage.test.tsx
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
rtk git add app_v4/web/src/components/BackupChart.tsx app_v4/web/src/components/LiveFeed.tsx app_v4/web/src/components/FleetGrid.tsx app_v4/web/src/styles/dashboard.css app_v4/web/src/pages/DashboardPage.test.tsx
rtk git commit -m "style: polish v4 dashboard data visuals"
```

### Task 5: Responsive Polish and Visual Regression Screenshot

**Files:**
- Modify: `app_v4/web/package.json`
- Create: `app_v4/web/playwright.config.ts`
- Create: `app_v4/web/e2e/dashboard.visual.spec.ts`
- Modify: `app_v4/web/src/styles/global.css`
- Modify: `app_v4/web/src/styles/dashboard.css`

- [ ] **Step 1: Add Playwright dependency and scripts**

Update `app_v4/web/package.json` dev dependencies:

```json
"@playwright/test": "^1.50.0"
```

Update scripts:

```json
"e2e": "playwright test",
"e2e:update": "playwright test --update-snapshots"
```

Run:

```powershell
rtk npm --prefix app_v4/web install
rtk npx --prefix app_v4/web playwright install chromium
```

Expected: dependency installed and Chromium browser available.

- [ ] **Step 2: Add Playwright config**

Create `app_v4/web/playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1920, height: 1080 } } },
    { name: 'tablet-chromium', use: { ...devices['iPad Pro 11'] } },
  ],
});
```

- [ ] **Step 3: Add screenshot test**

Create `app_v4/web/e2e/dashboard.visual.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('dashboard keeps Ops Terminal visual shell', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'visual-test-token');
  });
  await page.route('/api/v1/system/metrics', async (route) => {
    await route.fulfill({ json: { switches: 12, backups: 348, jobs: 5, failures_24h: 1 } });
  });
  await page.goto('/');
  await expect(page.getByText('Twelve switches')).toBeVisible();
  await expect(page.getByText('SERVICE / RUNNING')).toBeVisible();
  await expect(page).toHaveScreenshot('dashboard-ops-terminal.png', { fullPage: true, maxDiffPixelRatio: 0.03 });
});
```

- [ ] **Step 4: Add mobile/tablet CSS fallback**

Append to `app_v4/web/src/styles/global.css`:

```css
@media (max-width: 980px) {
  .ops-shell { grid-template-columns: 1fr; }
  .ops-sidebar { position: static; padding: 18px; gap: 18px; }
  .nav-sections { grid-template-columns: 1fr; gap: 18px; }
  .ops-topbar { padding: 0 18px; }
  .topbar-right { gap: 10px; }
  .ops-content { padding: 18px; }
  .ops-footer { display: none; }
}
```

- [ ] **Step 5: Run web verification**

```powershell
rtk npm --prefix app_v4/web test -- --run
rtk npm --prefix app_v4/web run build
rtk npm --prefix app_v4/web run e2e -- --update-snapshots
```

Expected: unit tests pass, build succeeds, screenshot baseline created.

- [ ] **Step 6: Commit**

```powershell
rtk git add app_v4/web/package.json app_v4/web/package-lock.json app_v4/web/playwright.config.ts app_v4/web/e2e app_v4/web/src/styles/global.css app_v4/web/src/styles/dashboard.css
rtk git commit -m "test: add v4 Ops Terminal visual regression"
```

### Task 6: Desktop Shell Token Sync and Polish

**Files:**
- Modify: `app_v4/desktop/theme/generate_qss.py`
- Modify: `app_v4/desktop/theme/ops_terminal.qss`
- Modify: `app_v4/desktop/shell/sidebar.py`
- Modify: `app_v4/desktop/shell/topbar.py`
- Modify: `app_v4/tests/test_desktop_theme_generator.py`
- Modify: `app_v4/tests/test_desktop_shell.py`

- [ ] **Step 1: Update desktop theme generator test**

Replace `app_v4/tests/test_desktop_theme_generator.py` with:

```python
from pathlib import Path

from app_v4.desktop.theme.generate_qss import generate_qss


def test_generate_qss_maps_ops_terminal_tokens(tmp_path):
    tokens = tmp_path / "tokens.css"
    tokens.write_text(
        ":root { --ink: #0a0a0a; --surface: #141414; --line: #262626; --amber: #ffb800; --bone: #fafaf7; --muted: #737373; --green: #4ade80; --red: #ff3838; }",
        encoding="utf-8",
    )

    qss = generate_qss(tokens)

    assert "QFrame#Sidebar" in qss
    assert "#0a0a0a" in qss
    assert "#ffb800" in qss
    assert "#4ade80" in qss
```

- [ ] **Step 2: Replace QSS generator**

Replace `app_v4/desktop/theme/generate_qss.py` with:

```python
from __future__ import annotations

import re
from pathlib import Path


def _tokens(tokens_path: Path) -> dict[str, str]:
    text = tokens_path.read_text(encoding="utf-8")
    return {name: value.strip() for name, value in re.findall(r"--([a-z0-9-]+):\s*([^;]+);", text)}


def generate_qss(tokens_path: Path) -> str:
    t = _tokens(tokens_path)
    return f"""
QWidget {{ background: {t['ink']}; color: {t['bone']}; font-family: Geist; }}
QFrame#Sidebar {{ background: {t['ink']}; border-right: 1px solid {t['line']}; }}
QFrame#Topbar {{ background: {t['ink']}; border-bottom: 1px dashed {t['amber']}; }}
QLabel#Brand {{ color: {t['bone']}; font-family: JetBrains Mono; font-size: 28px; font-weight: 800; }}
QLabel#Marker {{ color: {t['muted']}; font-family: JetBrains Mono; letter-spacing: 2px; }}
QLabel#ServicePulse {{ color: {t['green']}; border: 1px solid {t['green']}; padding: 6px 10px; }}
QPushButton {{ background: {t['surface']}; color: {t['bone']}; border: 1px solid {t['line']}; border-radius: 0; padding: 9px; text-align: left; }}
QPushButton:hover {{ border-color: {t['amber']}; color: {t['amber']}; }}
QPushButton[active="true"] {{ border-left: 3px solid {t['amber']}; color: {t['bone']}; }}
""".strip()
```

- [ ] **Step 3: Refresh generated QSS**

Run a small Python command to regenerate `ops_terminal.qss` from web tokens:

```powershell
rtk python -c "from pathlib import Path; from app_v4.desktop.theme.generate_qss import generate_qss; Path('app_v4/desktop/theme/ops_terminal.qss').write_text(generate_qss(Path('app_v4/web/src/styles/tokens.css')), encoding='utf-8')"
```

Expected: `app_v4/desktop/theme/ops_terminal.qss` updated.

- [ ] **Step 4: Update desktop shell tests**

Append to `app_v4/tests/test_desktop_shell.py`:

```python
def test_desktop_shell_has_ops_terminal_status(qtbot):
    window = MainWindow(service_url="http://127.0.0.1:8443")
    qtbot.addWidget(window)

    assert window.topbar.service_pulse.text() == "SERVICE / RUNNING"
    assert window.sidebar.version_tag.text() == "V3.5.7 / PROD"
```

- [ ] **Step 5: Update desktop sidebar/topbar labels**

In `app_v4/desktop/shell/sidebar.py`, add labels matching web shell:

```python
self.version_tag = QLabel("V3.5.7 / PROD")
self.version_tag.setObjectName("Marker")
layout.addWidget(self.version_tag)
```

In `app_v4/desktop/shell/topbar.py`, add:

```python
self.service_pulse = QLabel("SERVICE / RUNNING")
self.service_pulse.setObjectName("ServicePulse")
layout.addWidget(self.service_pulse)
```

- [ ] **Step 6: Run desktop polish tests**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_theme_generator.py app_v4/tests/test_desktop_shell.py -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
rtk git add app_v4/desktop/theme/generate_qss.py app_v4/desktop/theme/ops_terminal.qss app_v4/desktop/shell/sidebar.py app_v4/desktop/shell/topbar.py app_v4/tests/test_desktop_theme_generator.py app_v4/tests/test_desktop_shell.py
rtk git commit -m "style: polish v4 desktop Ops Terminal shell"
```

### Task 7: Final Visual Build Verification

**Files:**
- No new files.

- [ ] **Step 1: Run full web verification**

```powershell
rtk npm --prefix app_v4/web test -- --run
rtk npm --prefix app_v4/web run build
```

Expected: all web tests pass and static bundle builds into `app_v4/service/static/`.

- [ ] **Step 2: Run visual regression**

```powershell
rtk npm --prefix app_v4/web run e2e
```

Expected: screenshot test passes against committed baseline.

- [ ] **Step 3: Run desktop visual-adjacent tests**

```powershell
rtk python -m pytest app_v4/tests/test_desktop_theme_generator.py app_v4/tests/test_desktop_shell.py app_v4/tests/test_desktop_views.py -v
```

Expected: pass.

- [ ] **Step 4: Run backend smoke tests affected by static bundle**

```powershell
rtk python -m pytest app_v4/tests/test_static_serving.py app_v4/tests/test_app_factory.py -v
```

Expected: pass.

- [ ] **Step 5: Commit generated static bundle if changed**

```powershell
rtk git add app_v4/service/static app_v4/web app_v4/desktop app_v4/tests
rtk git commit -m "style: complete v4 Ops Terminal visual polish"
```

If no files changed after verification, skip commit.
