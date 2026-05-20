# NCM v4 Phase 5 Web Management Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete remaining React web client pages: switches, credentials, history, diff, schedules, users, and settings.

**Architecture:** Build pages on the Phase 4 shell and typed API client. Use TanStack Query hooks per domain, drawer-style forms for create/update flows, write-only credential secrets, and role-aware navigation guards.

**Tech Stack:** React 18, TypeScript, Vite, TanStack Query v5, Wouter, Zustand, Vitest, Testing Library.

---

## File Structure

- Modify: `app_v4/web/src/App.tsx` — add routes for all pages.
- Modify: `app_v4/web/src/api/types.ts` — add Switch, Credential, Backup, Job, User, Audit types.
- Modify: `app_v4/web/src/api/hooks.ts` — add query/mutation hooks.
- Modify: `app_v4/web/src/layout/Sidebar.tsx` — keep links active for all pages.
- Create: `app_v4/web/src/components/DataTable.tsx` — shared sharp table.
- Create: `app_v4/web/src/components/Drawer.tsx` — shared drawer shell.
- Create: `app_v4/web/src/components/ProblemToast.tsx` — display problem-details errors.
- Create: `app_v4/web/src/pages/SwitchesPage.tsx`
- Create: `app_v4/web/src/pages/CredentialsPage.tsx`
- Create: `app_v4/web/src/pages/HistoryPage.tsx`
- Create: `app_v4/web/src/pages/DiffPage.tsx`
- Create: `app_v4/web/src/pages/SchedulesPage.tsx`
- Create: `app_v4/web/src/pages/UsersPage.tsx`
- Create: `app_v4/web/src/pages/SettingsPage.tsx`
- Test: `app_v4/web/src/pages/SwitchesPage.test.tsx`
- Test: `app_v4/web/src/pages/CredentialsPage.test.tsx`
- Test: `app_v4/web/src/pages/HistoryPage.test.tsx`
- Test: `app_v4/web/src/pages/SchedulesPage.test.tsx`
- Test: `app_v4/web/src/pages/UsersPage.test.tsx`

### Task 1: Shared Web API Types and Hooks

**Files:**
- Modify: `app_v4/web/src/api/types.ts`
- Modify: `app_v4/web/src/api/hooks.ts`

- [ ] **Step 1: Extend API types**

Add to `app_v4/web/src/api/types.ts`:

```ts
export interface SwitchRecord { id: number; name: string; host: string; protocol: string; port: number; credential_id: number; is_active: boolean; }
export interface CredentialRecord { id: number; name: string; username?: string; created_at?: string; updated_at?: string; }
export interface BackupRecord { id: number; switch_id: number; backup_type: string; success: boolean; file_path?: string | null; created_at: string; message?: string | null; }
export interface JobRecord { id: number; switch_id: number; name: string; interval_minutes: number; schedule_hour: number; schedule_minute: number; enabled: boolean; last_run_at?: string | null; }
export interface UserRecord { id: number; username: string; role: Role; is_active: boolean; created_at: string; last_login_at?: string | null; }
export interface ProblemDetails { type: string; title: string; status: number; detail: string; }
```

- [ ] **Step 2: Add hooks**

Add to `app_v4/web/src/api/hooks.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { BackupRecord, CredentialRecord, JobRecord, SwitchRecord, UserRecord } from './types';

export function useSwitches() { return useQuery({ queryKey: ['switches'], queryFn: async () => (await api.get<SwitchRecord[]>('/switches')).data }); }
export function useCredentials() { return useQuery({ queryKey: ['credentials'], queryFn: async () => (await api.get<CredentialRecord[]>('/credentials')).data }); }
export function useBackups(switchId?: number) { return useQuery({ queryKey: ['backups', switchId], queryFn: async () => (await api.get<BackupRecord[]>('/backups', { params: { switch_id: switchId } })).data }); }
export function useJobs() { return useQuery({ queryKey: ['jobs'], queryFn: async () => (await api.get<JobRecord[]>('/jobs')).data }); }
export function useUsers() { return useQuery({ queryKey: ['users'], queryFn: async () => (await api.get<UserRecord[]>('/users')).data }); }

export function useTriggerBackup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (switchId: number) => (await api.post(`/switches/${switchId}/backup`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backups'] }),
  });
}
```

- [ ] **Step 3: Typecheck**

```powershell
rtk npm --prefix app_v4/web run build
```

Expected: build passes or fails only because pages are not routed yet.

### Task 2: Shared Table, Drawer, and Error Components

**Files:**
- Create: `app_v4/web/src/components/DataTable.tsx`
- Create: `app_v4/web/src/components/Drawer.tsx`
- Create: `app_v4/web/src/components/ProblemToast.tsx`

- [ ] **Step 1: Create `DataTable`**

```tsx
export function DataTable<T>({ rows, columns }: { rows: T[]; columns: { key: string; label: string; render: (row: T) => React.ReactNode }[] }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid var(--line)' }}>
      <thead><tr>{columns.map((column) => <th className="marker" style={{ textAlign: 'left', padding: 12 }} key={column.key}>{column.label}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column) => <td style={{ borderTop: '1px dashed var(--line-2)', padding: 12 }} key={column.key}>{column.render(row)}</td>)}</tr>)}</tbody>
    </table>
  );
}
```

- [ ] **Step 2: Create `Drawer`**

```tsx
import type { ReactNode } from 'react';

export function Drawer({ title, open, children, onClose }: { title: string; open: boolean; children: ReactNode; onClose: () => void }) {
  if (!open) return null;
  return <aside style={{ position: 'fixed', right: 0, top: 0, bottom: 0, width: 420, background: 'var(--surface)', borderLeft: '1px solid var(--amber)', padding: 24 }}><button onClick={onClose}>Close</button><h2>{title}</h2>{children}</aside>;
}
```

- [ ] **Step 3: Create `ProblemToast`**

```tsx
import type { ProblemDetails } from '../api/types';

export function ProblemToast({ problem }: { problem: ProblemDetails | null }) {
  if (!problem) return null;
  return <div role="alert" style={{ border: '1px solid var(--red)', padding: 12 }}><span className="marker">/ERR-{problem.type}</span><p>{problem.detail}</p></div>;
}
```

### Task 3: Switches Page

**Files:**
- Create: `app_v4/web/src/pages/SwitchesPage.tsx`
- Create: `app_v4/web/src/pages/SwitchesPage.test.tsx`
- Modify: `app_v4/web/src/App.tsx`

- [ ] **Step 1: Write test**

Create `app_v4/web/src/pages/SwitchesPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SwitchesPage } from './SwitchesPage';

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [{ id: 1, name: 'sw01', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true }], isLoading: false }),
  useTriggerBackup: () => ({ mutate: vi.fn(), isPending: false }),
}));

it('renders switches and backup action', () => {
  render(<QueryClientProvider client={new QueryClient()}><SwitchesPage /></QueryClientProvider>);
  expect(screen.getByText('sw01')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /backup now/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Create page**

Create `app_v4/web/src/pages/SwitchesPage.tsx`:

```tsx
import { DataTable } from '../components/DataTable';
import { useSwitches, useTriggerBackup } from '../api/hooks';
import type { SwitchRecord } from '../api/types';

export function SwitchesPage() {
  const { data = [] } = useSwitches();
  const backup = useTriggerBackup();
  return (
    <main>
      <p className="marker">/02 · INV</p>
      <h1 className="headline">Inventory, sharpened for operators.</h1>
      <DataTable<SwitchRecord> rows={data} columns={[
        { key: 'name', label: 'Name', render: (row) => row.name },
        { key: 'host', label: 'Host', render: (row) => row.host },
        { key: 'protocol', label: 'Protocol', render: (row) => row.protocol },
        { key: 'action', label: 'Action', render: (row) => <button onClick={() => backup.mutate(row.id)}>Backup now</button> },
      ]} />
    </main>
  );
}
```

- [ ] **Step 3: Add route**

In `App.tsx`, add:

```tsx
<Route path="/switches" component={SwitchesPage} />
```

- [ ] **Step 4: Run test**

```powershell
rtk npm --prefix app_v4/web test -- --run src/pages/SwitchesPage.test.tsx
```

Expected: pass.

### Task 4: Credentials and Schedules Pages

**Files:**
- Create: `app_v4/web/src/pages/CredentialsPage.tsx`
- Create: `app_v4/web/src/pages/SchedulesPage.tsx`
- Create: `app_v4/web/src/pages/CredentialsPage.test.tsx`
- Create: `app_v4/web/src/pages/SchedulesPage.test.tsx`
- Modify: `app_v4/web/src/App.tsx`

- [ ] **Step 1: Create credentials page**

`CredentialsPage.tsx`:

```tsx
import { DataTable } from '../components/DataTable';
import { useCredentials } from '../api/hooks';
import type { CredentialRecord } from '../api/types';

export function CredentialsPage() {
  const { data = [] } = useCredentials();
  return <main><p className="marker">/03 · CREDS</p><h1 className="headline">Credentials stay write-only.</h1><DataTable<CredentialRecord> rows={data} columns={[{ key: 'name', label: 'Name', render: (row) => row.name }, { key: 'secret', label: 'Secret', render: () => '••••••••' }]} /></main>;
}
```

- [ ] **Step 2: Create schedules page**

`SchedulesPage.tsx`:

```tsx
import { DataTable } from '../components/DataTable';
import { useJobs } from '../api/hooks';
import type { JobRecord } from '../api/types';

export function SchedulesPage() {
  const { data = [] } = useJobs();
  return <main><p className="marker">/04 · SCH</p><h1 className="headline">Schedules run without watchers.</h1><DataTable<JobRecord> rows={data} columns={[{ key: 'name', label: 'Name', render: (row) => row.name }, { key: 'interval', label: 'Interval', render: (row) => `${row.interval_minutes}m` }, { key: 'enabled', label: 'State', render: (row) => row.enabled ? 'enabled' : 'disabled' }]} /></main>;
}
```

- [ ] **Step 3: Add tests**

Create tests that mock `useCredentials` and `useJobs`, then assert headline and row text render. Use the `SwitchesPage.test.tsx` pattern.

- [ ] **Step 4: Add routes and run tests**

```powershell
rtk npm --prefix app_v4/web test -- --run src/pages/CredentialsPage.test.tsx src/pages/SchedulesPage.test.tsx
```

Expected: pass.

### Task 5: History and Diff Pages

**Files:**
- Create: `app_v4/web/src/pages/HistoryPage.tsx`
- Create: `app_v4/web/src/pages/DiffPage.tsx`
- Create: `app_v4/web/src/pages/HistoryPage.test.tsx`
- Modify: `app_v4/web/src/App.tsx`

- [ ] **Step 1: Create pages**

`HistoryPage.tsx`:

```tsx
import { DataTable } from '../components/DataTable';
import { useBackups } from '../api/hooks';
import type { BackupRecord } from '../api/types';

export function HistoryPage() {
  const { data = [] } = useBackups();
  return <main><p className="marker">/05 · HIST</p><h1 className="headline">Every config has a trail.</h1><DataTable<BackupRecord> rows={data} columns={[{ key: 'id', label: 'ID', render: (row) => row.id }, { key: 'type', label: 'Type', render: (row) => row.backup_type }, { key: 'state', label: 'State', render: (row) => row.success ? 'success' : 'failed' }]} /></main>;
}
```

`DiffPage.tsx`:

```tsx
import { useState } from 'react';
import { api } from '../api/client';

export function DiffPage() {
  const [left, setLeft] = useState('');
  const [right, setRight] = useState('');
  const [diff, setDiff] = useState('');
  async function load() { setDiff((await api.get('/backups/diff', { params: { a: left, b: right }, responseType: 'text' })).data); }
  return <main><p className="marker">/06 · DIFF</p><h1 className="headline">Diffs expose drift.</h1><input aria-label="left backup" value={left} onChange={(e) => setLeft(e.target.value)} /><input aria-label="right backup" value={right} onChange={(e) => setRight(e.target.value)} /><button onClick={load}>Compare</button><pre>{diff}</pre></main>;
}
```

- [ ] **Step 2: Add history test**

Mock `useBackups` and assert backup id/state render.

- [ ] **Step 3: Add routes and run tests**

```powershell
rtk npm --prefix app_v4/web test -- --run src/pages/HistoryPage.test.tsx
```

Expected: pass.

### Task 6: Users and Settings Pages

**Files:**
- Create: `app_v4/web/src/pages/UsersPage.tsx`
- Create: `app_v4/web/src/pages/SettingsPage.tsx`
- Create: `app_v4/web/src/pages/UsersPage.test.tsx`
- Modify: `app_v4/web/src/App.tsx`

- [ ] **Step 1: Create users page**

`UsersPage.tsx`:

```tsx
import { DataTable } from '../components/DataTable';
import { useUsers } from '../api/hooks';
import type { UserRecord } from '../api/types';

export function UsersPage() {
  const { data = [] } = useUsers();
  return <main><p className="marker">/07 · USERS</p><h1 className="headline">Access is operational control.</h1><DataTable<UserRecord> rows={data} columns={[{ key: 'username', label: 'Username', render: (row) => row.username }, { key: 'role', label: 'Role', render: (row) => row.role }, { key: 'active', label: 'Active', render: (row) => row.is_active ? 'yes' : 'no' }]} /></main>;
}
```

- [ ] **Step 2: Create settings page**

`SettingsPage.tsx`:

```tsx
export function SettingsPage() {
  return <main><p className="marker">/08 · SETTINGS</p><h1 className="headline">Service, branding, retention, logs, about.</h1><section><h2>Service</h2><p>Bind address and service state.</p></section><section><h2>Retention</h2><p>Backup and audit retention windows.</p></section></main>;
}
```

- [ ] **Step 3: Add users test and routes**

Mock `useUsers`, assert username and role render, then add routes for `/users` and `/settings`.

- [ ] **Step 4: Full web verification**

```powershell
rtk npm --prefix app_v4/web test -- --run
rtk npm --prefix app_v4/web run build
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
rtk git add app_v4/web app_v4/service/static
rtk git commit -m "feat: add v4 web management pages"
```
