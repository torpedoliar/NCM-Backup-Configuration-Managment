# Phase 2 — Dashboard Real Data + Working Buttons

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every hardcoded value on the Dashboard with real data from the API or live WebSocket; wire every visible button to a working handler; make sidebar counts dynamic.

**Architecture:** Pure frontend. Dashboard widgets become React components subscribed to React Query hooks (already wired to `/api/v1/...`). Live events are buffered in a small Zustand store fed by the existing `useLiveSocket` hook. Time-range becomes a URL-synced state. EXPORT becomes an in-browser CSV builder. No backend change in this phase.

**Tech Stack:** React 18, React Query, Zustand, Wouter, vitest.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 2.

---

## Task 1: Live event store

**Files:**
- Create: `app_v4/web/src/store/live-events.ts`
- Create: `app_v4/web/src/store/live-events.test.ts`

- [ ] **Step 1: Write the failing test**

Create `app_v4/web/src/store/live-events.test.ts`:

```ts
import { describe, expect, it, beforeEach } from 'vitest';
import { useLiveEvents } from './live-events';

describe('live-events store', () => {
  beforeEach(() => {
    useLiveEvents.getState().clear();
  });

  it('appends events in order, newest first', () => {
    useLiveEvents.getState().push({ type: 'backup_completed', payload: { switch_name: 'A' }, ts: '2026-05-20T01:00:00Z' });
    useLiveEvents.getState().push({ type: 'backup_completed', payload: { switch_name: 'B' }, ts: '2026-05-20T01:01:00Z' });
    expect(useLiveEvents.getState().events.map((e) => e.payload.switch_name)).toEqual(['B', 'A']);
  });

  it('caps the buffer at 50 events', () => {
    for (let i = 0; i < 60; i++) {
      useLiveEvents.getState().push({ type: 'x', payload: { i }, ts: new Date().toISOString() });
    }
    expect(useLiveEvents.getState().events.length).toBe(50);
    expect(useLiveEvents.getState().events[0].payload.i).toBe(59);
  });

  it('reports last 24h count', () => {
    const now = Date.now();
    useLiveEvents.getState().push({ type: 'x', payload: {}, ts: new Date(now - 1000).toISOString() });
    useLiveEvents.getState().push({ type: 'x', payload: {}, ts: new Date(now - 25 * 3600 * 1000).toISOString() });
    expect(useLiveEvents.getState().countLast24h()).toBe(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix app_v4/web test -- --run src/store/live-events.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the store**

Create `app_v4/web/src/store/live-events.ts`:

```ts
import { create } from 'zustand';
import type { LiveEvent } from '../api/types';

const MAX_EVENTS = 50;

interface LiveEventsState {
  events: LiveEvent[];
  push: (event: LiveEvent) => void;
  clear: () => void;
  countLast24h: () => number;
}

export const useLiveEvents = create<LiveEventsState>((set, get) => ({
  events: [],
  push: (event) =>
    set((state) => ({
      events: [event, ...state.events].slice(0, MAX_EVENTS),
    })),
  clear: () => set({ events: [] }),
  countLast24h: () => {
    const cutoff = Date.now() - 24 * 60 * 60 * 1000;
    return get().events.filter((e) => Date.parse(e.ts) >= cutoff).length;
  },
}));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix app_v4/web test -- --run src/store/live-events.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app_v4/web/src/store/live-events.ts app_v4/web/src/store/live-events.test.ts
git commit -m "feat(dashboard): live events store"
```

---

## Task 2: Wire `useLiveSocket` to the store

**Files:**
- Modify: `app_v4/web/src/lib/ws.ts`

- [ ] **Step 1: Read the current implementation**

Run: `cat app_v4/web/src/lib/ws.ts`
Note: it currently opens a WebSocket and returns nothing. Find the `onmessage` handler.

- [ ] **Step 2: Modify `onmessage` to push to the store**

Edit `app_v4/web/src/lib/ws.ts`:
- Add `import { useLiveEvents } from '../store/live-events';` near the top.
- In the `onmessage` handler, after parsing JSON into `data`, call `useLiveEvents.getState().push(data as LiveEvent);` if `data && typeof data === 'object' && 'type' in data && 'ts' in data`.

- [ ] **Step 3: Run all tests to confirm nothing else broke**

Run: `npm --prefix app_v4/web test -- --run`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add app_v4/web/src/lib/ws.ts
git commit -m "feat(dashboard): pipe websocket events into live store"
```

---

## Task 3: `LiveFeed` reads from the store

**Files:**
- Modify: `app_v4/web/src/components/LiveFeed.tsx`
- Create: `app_v4/web/src/components/LiveFeed.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `app_v4/web/src/components/LiveFeed.test.tsx`:

```tsx
import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LiveFeed } from './LiveFeed';
import { useLiveEvents } from '../store/live-events';

describe('LiveFeed', () => {
  beforeEach(() => useLiveEvents.getState().clear());

  it('renders events from the live store newest first', () => {
    useLiveEvents.getState().push({
      type: 'backup_completed',
      payload: { switch_name: 'SW-CORE-01', backup_id: 1 },
      ts: '2026-05-20T01:00:00Z',
    });
    useLiveEvents.getState().push({
      type: 'backup_failed',
      payload: { switch_name: 'SW-EDGE-07', message: 'timeout' },
      ts: '2026-05-20T01:01:00Z',
    });

    render(<LiveFeed />);

    const items = screen.getAllByRole('listitem');
    expect(items[0].textContent).toContain('SW-EDGE-07');
    expect(items[1].textContent).toContain('SW-CORE-01');
  });

  it('shows an empty state when there are no events', () => {
    render(<LiveFeed />);
    expect(screen.getByText(/no recent activity/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix app_v4/web test -- --run src/components/LiveFeed.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Replace `LiveFeed.tsx` to consume the store**

Overwrite `app_v4/web/src/components/LiveFeed.tsx`:

```tsx
import { useLiveEvents } from '../store/live-events';

function describe(event: { type: string; payload: Record<string, unknown> }): string {
  const name = (event.payload.switch_name as string | undefined) ?? '';
  switch (event.type) {
    case 'backup_completed':
      return `${name} backup completed`.trim();
    case 'backup_failed':
      return `${name} backup failed${event.payload.message ? `: ${event.payload.message}` : ''}`.trim();
    case 'backup_started':
      return `${name} backup started`.trim();
    case 'job_triggered':
      return `Scheduled job triggered (switch ${event.payload.switch_id ?? '?'})`;
    default:
      return event.type;
  }
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString();
}

export function LiveFeed() {
  const events = useLiveEvents((s) => s.events);
  const count = useLiveEvents((s) => s.countLast24h());

  if (events.length === 0) {
    return <p className="muted">No recent activity yet.</p>;
  }

  return (
    <div className="live-feed">
      <ul role="list">
        {events.map((event, idx) => (
          <li key={`${event.ts}-${idx}`}>
            <span className="ts">{fmtTime(event.ts)}</span>
            <span className={`evt evt-${event.type}`}>{describe(event)}</span>
          </li>
        ))}
      </ul>
      <footer className="live-feed-footer">
        <span><b>{count}</b> EVENTS / 24H</span>
      </footer>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix app_v4/web test -- --run src/components/LiveFeed.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app_v4/web/src/components/LiveFeed.tsx app_v4/web/src/components/LiveFeed.test.tsx
git commit -m "feat(dashboard): LiveFeed reads from real-time event store"
```

---

## Task 4: `FleetGrid` from API

**Files:**
- Modify: `app_v4/web/src/components/FleetGrid.tsx`
- Create: `app_v4/web/src/components/FleetGrid.test.tsx`
- Modify: `app_v4/web/src/api/hooks.ts`

- [ ] **Step 1: Add a `useLatestBackupPerSwitch` hook**

Edit `app_v4/web/src/api/hooks.ts`. Append at the end:

```ts
export function useLatestBackupPerSwitch() {
  return useQuery({
    queryKey: ['backups', 'latest-per-switch'],
    queryFn: async () => (await api.get<BackupRecord[]>('/backups', { params: { limit: 1000 } })).data,
    staleTime: 30 * SECOND,
  });
}
```

- [ ] **Step 2: Write the failing test**

Create `app_v4/web/src/components/FleetGrid.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FleetGrid } from './FleetGrid';

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({
    data: [
      { id: 1, name: 'SW-CORE-01', ip: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
      { id: 2, name: 'SW-EDGE-07', ip: '10.0.0.2', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
    ],
    isLoading: false,
  }),
  useLatestBackupPerSwitch: () => ({
    data: [
      { id: 5, switch_id: 1, backup_type: 'manual', success: true, created_at: new Date().toISOString() },
      { id: 6, switch_id: 2, backup_type: 'manual', success: false, created_at: new Date(Date.now() - 3600 * 1000).toISOString(), message: 'timeout' },
    ],
    isLoading: false,
  }),
}));

describe('FleetGrid', () => {
  it('renders one cell per switch with status derived from last backup', () => {
    render(<FleetGrid />);
    const cells = screen.getAllByRole('listitem');
    expect(cells).toHaveLength(2);
    expect(cells[0]).toHaveAttribute('data-state', 'ok');
    expect(cells[1]).toHaveAttribute('data-state', 'fail');
  });

  it('shows empty state when no switches', () => {
    vi.resetModules();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm --prefix app_v4/web test -- --run src/components/FleetGrid.test.tsx`
Expected: FAIL — current FleetGrid is hardcoded.

- [ ] **Step 4: Replace `FleetGrid.tsx`**

Overwrite `app_v4/web/src/components/FleetGrid.tsx`:

```tsx
import { useLatestBackupPerSwitch, useSwitches } from '../api/hooks';
import type { BackupRecord, SwitchRecord } from '../api/types';

type State = 'ok' | 'warn' | 'fail' | 'unknown';

const WARN_AFTER_MS = 24 * 60 * 60 * 1000;

function deriveState(latest: BackupRecord | undefined): State {
  if (!latest) return 'unknown';
  if (!latest.success) return 'fail';
  const age = Date.now() - Date.parse(latest.created_at);
  return age > WARN_AFTER_MS ? 'warn' : 'ok';
}

function ageLabel(latest: BackupRecord | undefined): string {
  if (!latest) return '—';
  const ms = Date.now() - Date.parse(latest.created_at);
  if (Number.isNaN(ms)) return '—';
  const minutes = Math.floor(ms / 60000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

export function FleetGrid() {
  const { data: switches = [] } = useSwitches();
  const { data: backups = [] } = useLatestBackupPerSwitch();

  const latestBySwitch = new Map<number, BackupRecord>();
  for (const backup of backups) {
    const existing = latestBySwitch.get(backup.switch_id);
    if (!existing || Date.parse(backup.created_at) > Date.parse(existing.created_at)) {
      latestBySwitch.set(backup.switch_id, backup);
    }
  }

  if (switches.length === 0) {
    return <p className="muted">No switches under management yet.</p>;
  }

  return (
    <ul role="list" className="fleet-grid">
      {switches.map((sw: SwitchRecord) => {
        const latest = latestBySwitch.get(sw.id);
        const state = deriveState(latest);
        return (
          <li key={sw.id} role="listitem" data-state={state} title={`${sw.ip} · ${sw.protocol}`}>
            <span className="fleet-name">{sw.name}</span>
            <span className={`fleet-state state-${state}`}>{state.toUpperCase()}</span>
            <span className="fleet-age">{ageLabel(latest)}</span>
          </li>
        );
      })}
    </ul>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm --prefix app_v4/web test -- --run src/components/FleetGrid.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app_v4/web/src/components/FleetGrid.tsx app_v4/web/src/components/FleetGrid.test.tsx app_v4/web/src/api/hooks.ts
git commit -m "feat(dashboard): FleetGrid sourced from /switches and /backups"
```

---

## Task 5: `BackupChart` from `/backups` bucketed per day

**Files:**
- Modify: `app_v4/web/src/components/BackupChart.tsx`
- Create: `app_v4/web/src/components/BackupChart.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `app_v4/web/src/components/BackupChart.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BackupChart } from './BackupChart';

vi.mock('../api/hooks', () => ({
  useBackups: () => ({
    data: [
      { id: 1, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-19T10:00:00Z' },
      { id: 2, switch_id: 1, backup_type: 'manual', success: false, created_at: '2026-05-19T10:01:00Z' },
      { id: 3, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-20T10:00:00Z' },
    ],
    isLoading: false,
  }),
}));

describe('BackupChart', () => {
  it('renders a bar per day in the requested range', () => {
    render(<BackupChart range="7d" />);
    const bars = document.querySelectorAll('[data-day-bar]');
    expect(bars.length).toBe(7);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix app_v4/web test -- --run src/components/BackupChart.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Replace `BackupChart.tsx`**

Overwrite `app_v4/web/src/components/BackupChart.tsx`:

```tsx
import { useBackups } from '../api/hooks';
import type { BackupRecord } from '../api/types';

export type DashboardRange = '24h' | '7d' | '30d' | '90d';

const DAYS_PER_RANGE: Record<DashboardRange, number> = { '24h': 1, '7d': 7, '30d': 30, '90d': 90 };

function dayKey(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function BackupChart({ range }: { range: DashboardRange }) {
  const { data = [] } = useBackups();
  const days = DAYS_PER_RANGE[range];
  const today = new Date();

  const buckets: { key: string; success: number; failed: number }[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setUTCDate(d.getUTCDate() - i);
    buckets.push({ key: dayKey(d), success: 0, failed: 0 });
  }
  const index = new Map(buckets.map((b, i) => [b.key, i]));

  for (const b of data as BackupRecord[]) {
    const k = dayKey(new Date(b.created_at));
    const i = index.get(k);
    if (i === undefined) continue;
    if (b.success) buckets[i].success += 1;
    else buckets[i].failed += 1;
  }

  const max = Math.max(1, ...buckets.map((b) => b.success + b.failed));

  return (
    <div className="backup-chart">
      {buckets.map((b) => (
        <div key={b.key} className="bar" data-day-bar data-key={b.key}>
          <div className="bar-success" style={{ height: `${(b.success / max) * 100}%` }} />
          <div className="bar-failed" style={{ height: `${(b.failed / max) * 100}%` }} />
          <span className="bar-label">{b.key.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix app_v4/web test -- --run src/components/BackupChart.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app_v4/web/src/components/BackupChart.tsx app_v4/web/src/components/BackupChart.test.tsx
git commit -m "feat(dashboard): BackupChart bucketed from real backups"
```

---

## Task 6: Dashboard hero, range tabs, EXPORT, sidebar counts

**Files:**
- Modify: `app_v4/web/src/pages/DashboardPage.tsx`
- Modify: `app_v4/web/src/pages/DashboardPage.test.tsx`
- Modify: `app_v4/web/src/layout/Sidebar.tsx`
- Create: `app_v4/web/src/layout/Sidebar.test.tsx`
- Create: `app_v4/web/src/lib/csv.ts`
- Create: `app_v4/web/src/lib/csv.test.ts`

- [ ] **Step 1: CSV helper test (RED)**

Create `app_v4/web/src/lib/csv.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { toCsv } from './csv';

describe('toCsv', () => {
  it('serialises rows with header and quoted strings', () => {
    const csv = toCsv(
      ['name', 'note'],
      [{ name: 'A', note: 'hello, world' }, { name: 'B', note: 'plain' }],
    );
    expect(csv).toBe('name,note\nA,"hello, world"\nB,plain\n');
  });

  it('escapes embedded quotes', () => {
    const csv = toCsv(['x'], [{ x: 'a "b" c' }]);
    expect(csv).toContain('"a ""b"" c"');
  });
});
```

Run: `npm --prefix app_v4/web test -- --run src/lib/csv.test.ts`
Expected: FAIL.

- [ ] **Step 2: Implement `toCsv`**

Create `app_v4/web/src/lib/csv.ts`:

```ts
function cell(value: unknown): string {
  if (value === null || value === undefined) return '';
  const s = typeof value === 'string' ? value : String(value);
  if (/[",\n]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function toCsv<T extends Record<string, unknown>>(headers: string[], rows: T[]): string {
  const lines = [headers.join(',')];
  for (const row of rows) {
    lines.push(headers.map((h) => cell(row[h])).join(','));
  }
  return lines.join('\n') + '\n';
}
```

Run: `npm --prefix app_v4/web test -- --run src/lib/csv.test.ts`
Expected: PASS.

- [ ] **Step 3: Sidebar dynamic counts test (RED)**

Create `app_v4/web/src/layout/Sidebar.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from './Sidebar';

vi.mock('../api/hooks', () => ({
  useSystemMetrics: () => ({
    data: { switches: 7, backups: 42, jobs: 3, failures_24h: 1 },
    isLoading: false,
  }),
}));

vi.mock('wouter', async () => {
  const actual = await vi.importActual<typeof import('wouter')>('wouter');
  return { ...actual, useLocation: () => ['/'] };
});

describe('Sidebar', () => {
  it('renders counts from /system/metrics', () => {
    render(<Sidebar />);
    expect(screen.getByText(/Switches/i).parentElement?.textContent).toContain('7');
    expect(screen.getByText(/Backup History/i).parentElement?.textContent).toContain('42');
    expect(screen.getByText(/Schedules/i).parentElement?.textContent).toContain('3');
  });
});
```

Run: `npm --prefix app_v4/web test -- --run src/layout/Sidebar.test.tsx`
Expected: FAIL — counts hardcoded.

- [ ] **Step 4: Update `Sidebar.tsx`**

Read current file: `cat app_v4/web/src/layout/Sidebar.tsx`. Replace the hardcoded `count` strings with values from `useSystemMetrics`. The replacement strategy:

- Add `import { useSystemMetrics } from '../api/hooks';`
- Inside `Sidebar`, call `const { data: metrics } = useSystemMetrics();` and a helper `const count = (n?: number) => (n === undefined ? '—' : String(n));`
- Replace each fixed count in the navigation arrays with `count(metrics?.switches)`, `count(metrics?.backups)`, `count(metrics?.jobs)`, `count(metrics?.users)` accordingly. (If `users` is not exposed by `/system/metrics`, leave as `count(undefined)` for now — Phase 3 will make Users count dynamic via separate query if needed.)

Run: `npm --prefix app_v4/web test -- --run src/layout/Sidebar.test.tsx`
Expected: PASS.

- [ ] **Step 5: Dashboard hero + range + EXPORT test (RED)**

Replace `app_v4/web/src/pages/DashboardPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Router } from 'wouter';
import { memoryLocation } from 'wouter/memory-location';
import { DashboardPage } from './DashboardPage';

vi.mock('../api/hooks', () => ({
  useSystemMetrics: () => ({ data: { switches: 7, backups: 42, jobs: 3, failures_24h: 0 }, isLoading: false }),
  useSwitches: () => ({ data: [], isLoading: false }),
  useBackups: () => ({ data: [], isLoading: false }),
  useLatestBackupPerSwitch: () => ({ data: [], isLoading: false }),
}));

vi.mock('../auth/AuthProvider', () => ({
  useOptionalAuth: () => null,
}));

vi.mock('../lib/ws', () => ({ useLiveSocket: () => undefined }));

function renderPage() {
  const { hook } = memoryLocation({ path: '/' });
  return render(
    <Router hook={hook}>
      <DashboardPage />
    </Router>,
  );
}

describe('DashboardPage', () => {
  it('renders the hero headline using metrics from the API', () => {
    renderPage();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('7');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('42');
  });

  it('time-range tabs change the active range', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole('button', { name: '7D' }));
    expect(screen.getByRole('button', { name: '7D' })).toHaveAttribute('data-active', 'true');
  });

  it('EXPORT triggers a CSV download', () => {
    const click = vi.fn();
    const original = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = click;
    try {
      renderPage();
      fireEvent.click(screen.getByRole('button', { name: /export/i }));
      expect(click).toHaveBeenCalled();
    } finally {
      HTMLAnchorElement.prototype.click = original;
    }
  });
});
```

Run: `npm --prefix app_v4/web test -- --run src/pages/DashboardPage.test.tsx`
Expected: FAIL.

- [ ] **Step 6: Replace `DashboardPage.tsx`**

Overwrite `app_v4/web/src/pages/DashboardPage.tsx`:

```tsx
import { useState } from 'react';
import { BackupChart, type DashboardRange } from '../components/BackupChart';
import { FleetGrid } from '../components/FleetGrid';
import { KpiCell } from '../components/KpiCell';
import { LiveFeed } from '../components/LiveFeed';
import { OpsPanel } from '../components/OpsPanel';
import { useBackups, useSystemMetrics } from '../api/hooks';
import { useOptionalAuth } from '../auth/AuthProvider';
import { useLiveSocket } from '../lib/ws';
import { number } from '../lib/fmt';
import { toCsv } from '../lib/csv';
import '../styles/dashboard.css';

const RANGES: DashboardRange[] = ['24h', '7d', '30d', '90d'];

function dash(value: number | undefined): string {
  return value === undefined ? '—' : number(value);
}

export function DashboardPage() {
  const { data: metrics } = useSystemMetrics();
  const { data: backups = [] } = useBackups();
  const auth = useOptionalAuth();
  useLiveSocket(auth?.accessToken ?? null);
  const [range, setRange] = useState<DashboardRange>('24h');

  const switches = metrics?.switches;
  const backupsCount = metrics?.backups;
  const failures = metrics?.failures_24h ?? 0;

  function exportCsv() {
    const rows = backups.map((b) => ({
      id: b.id,
      switch_id: b.switch_id,
      taken_at: b.created_at,
      success: b.success ? 'true' : 'false',
      backup_type: b.backup_type,
      size_bytes: b.size_bytes ?? 0,
      message: b.message ?? '',
    }));
    const csv = toCsv(['id', 'switch_id', 'taken_at', 'success', 'backup_type', 'size_bytes', 'message'], rows);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backups-${range}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="dashboard-page">
      <section className="dashboard-hero">
        <div>
          <div className="marker marker-amber">OPERATIONS OVERVIEW</div>
          <h1 className="headline hero-headline">
            {dash(switches)} switches, <em>{dash(backupsCount)}</em> backups, {failures} anomal{failures === 1 ? 'y' : 'ies'}.
          </h1>
          <div className="hero-underline" />
        </div>
        <div className="hero-meta">
          <span className="marker">/REF DSH-001</span>
          <span className="marker marker-amber">LIVE</span>
        </div>
      </section>

      <section className="range-tabs" aria-label="time range">
        {RANGES.map((r) => (
          <button
            key={r}
            data-active={r === range}
            className={r === range ? 'active' : ''}
            onClick={() => setRange(r)}
          >
            {r.toUpperCase()}
          </button>
        ))}
        <button onClick={exportCsv}>EXPORT ↗</button>
      </section>

      <section className="kpi-grid">
        <KpiCell marker="/01 · INV" label="SWITCHES UNDER MGMT" value={dash(switches)} />
        <KpiCell marker="/02 · EXEC" label="BACKUPS" value={dash(backupsCount)} />
        <KpiCell
          marker="/03 · QOS"
          label="SUCCESS RATE"
          value={
            backupsCount && backupsCount > 0
              ? (((backupsCount - failures) / backupsCount) * 100).toFixed(1)
              : '—'
          }
          suffix="%"
        />
        <KpiCell
          marker="/04 · ALERT"
          label="FAILED · 24H"
          value={String(failures).padStart(2, '0')}
          tone={failures > 0 ? 'red' : undefined}
        />
      </section>

      <section className="dashboard-grid">
        <OpsPanel marker="/05 · TIMESERIES" title={`Backup activity, last ${range}`} className="chart-panel">
          <BackupChart range={range} />
        </OpsPanel>
        <OpsPanel marker="/06 · STREAM" title="Live activity" className="live-panel">
          <LiveFeed />
        </OpsPanel>
      </section>

      <OpsPanel marker="/07 · FLEET" title="Switch fleet, at a glance" className="fleet-panel">
        <FleetGrid />
      </OpsPanel>
    </main>
  );
}
```

- [ ] **Step 7: Run dashboard tests**

Run: `npm --prefix app_v4/web test -- --run src/pages/DashboardPage.test.tsx src/layout/Sidebar.test.tsx`
Expected: PASS.

- [ ] **Step 8: Run full SPA suite**

Run: `npm --prefix app_v4/web test -- --run`
Expected: all green.

- [ ] **Step 9: Build to verify TS + Vite**

Run: `npm --prefix app_v4/web run build`
Expected: build OK.

- [ ] **Step 10: Commit**

```bash
git add app_v4/web/src/pages/DashboardPage.tsx app_v4/web/src/pages/DashboardPage.test.tsx \
        app_v4/web/src/layout/Sidebar.tsx app_v4/web/src/layout/Sidebar.test.tsx \
        app_v4/web/src/lib/csv.ts app_v4/web/src/lib/csv.test.ts
git commit -m "feat(dashboard): real metrics, working tabs, CSV export, dynamic sidebar counts"
```

---

## Task 7: Rebuild PyInstaller bundle

- [ ] **Step 1: Make sure no exe is running**

Run: `tasklist | rg ncm-v4-desktop || echo none`
Expected: `none`. If running, ask user.

- [ ] **Step 2: Rebuild**

Run: `powershell -ExecutionPolicy Bypass -File installer/v4/build_app.ps1 -SkipWebBuild`
Expected: `==> Build OK`.

- [ ] **Step 3: No commit (dist/ is build output).**
