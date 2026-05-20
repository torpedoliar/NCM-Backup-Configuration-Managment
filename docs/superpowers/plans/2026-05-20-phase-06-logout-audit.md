# Phase 6 — Logout Button + Audit Page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sign-out button in the sidebar; auto-logout on 401; admin Audit page at `/audit` reading filtered events from `/api/v1/audit`.

**Architecture:**
- Backend: `GET /audit` extends with action prefix, user_id, date range, offset; `Repository.list_audit` extended; `Repository.count_audit` new; `X-Total-Count` header on response.
- Frontend: `AuthProvider.logout()` action; sidebar button; `/audit` route + page; nav link admin-gated; 401 interceptor calls `logout()`.

**Tech Stack:** FastAPI, SQLAlchemy, React Query, Wouter, vitest, pytest.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 6.

---

## Task 1: Repository — `count_audit` and filter params

**Files:**
- Modify: `app_v4/data/repository.py`
- Modify: `app_v4/tests/test_repository.py`

- [ ] **Step 1: Write failing test**

Append to `app_v4/tests/test_repository.py`:

```python
@pytest.mark.asyncio
async def test_list_audit_filters_and_counts(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        await repo.add_audit(action="auth.login_success", user_id=1)
        await repo.add_audit(action="switch.created", user_id=1)
        await repo.add_audit(action="auth.login_failed", user_id=None)
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        all_rows = await repo.list_audit(limit=10)
        only_auth = await repo.list_audit(limit=10, action_prefix="auth.")
        only_user1 = await repo.list_audit(limit=10, user_id=1)
        total = await repo.count_audit(action_prefix="auth.")

    assert len(all_rows) == 3
    assert all(r.action.startswith("auth.") for r in only_auth)
    assert all(r.user_id == 1 for r in only_user1)
    assert total == 2
```

If `add_audit` doesn't exist, `AuditWriter.record` is the existing path — for the test, write rows directly via the model:

```python
from app_v4.data.models import AuditLog
async with session_factory() as session:
    session.add(AuditLog(action="auth.login_success", user_id=1))
    session.add(AuditLog(action="switch.created", user_id=1))
    session.add(AuditLog(action="auth.login_failed", user_id=None))
    await session.commit()
```

Use that approach instead of `add_audit`.

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Extend `list_audit` and add `count_audit`**

```python
async def list_audit(
    self,
    limit: int = 100,
    offset: int = 0,
    action_prefix: str | None = None,
    user_id: int | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit).offset(offset)
    if action_prefix is not None:
        stmt = stmt.where(AuditLog.action.like(f"{action_prefix}%"))
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if from_ts is not None:
        stmt = stmt.where(AuditLog.ts >= from_ts)
    if to_ts is not None:
        stmt = stmt.where(AuditLog.ts <= to_ts)
    result = await self.session.execute(stmt)
    return list(result.scalars().all())

async def count_audit(
    self,
    action_prefix: str | None = None,
    user_id: int | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> int:
    stmt = select(func.count(AuditLog.id))
    if action_prefix is not None:
        stmt = stmt.where(AuditLog.action.like(f"{action_prefix}%"))
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if from_ts is not None:
        stmt = stmt.where(AuditLog.ts >= from_ts)
    if to_ts is not None:
        stmt = stmt.where(AuditLog.ts <= to_ts)
    result = await self.session.execute(stmt)
    return int(result.scalar_one())
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/data/repository.py app_v4/tests/test_repository.py
git commit -m "feat(repository): list_audit filters + count_audit"
```

---

## Task 2: API filters + `X-Total-Count` header

**Files:**
- Modify: `app_v4/service/api/audit.py`
- Modify: `app_v4/tests/test_audit_api.py`

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_list_audit_action_prefix(client, admin_token, seeded_audit):
    r = await client.get(
        "/api/v1/audit?action=auth.",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert all(row["action"].startswith("auth.") for row in r.json())
    assert "X-Total-Count" in r.headers


@pytest.mark.asyncio
async def test_audit_endpoint_pagination(client, admin_token, seeded_audit):
    r = await client.get(
        "/api/v1/audit?limit=2&offset=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()) <= 2
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Update endpoint**

Edit `app_v4/service/api/audit.py`:

```python
@router.get("/audit", response_model=list[AuditOut])
async def list_audit(
    response: Response,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, alias="action"),
    user_id: int | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role("admin")),
) -> list[AuditOut]:
    repo = Repository(session)
    rows = await repo.list_audit(
        limit=limit, offset=offset, action_prefix=action,
        user_id=user_id, from_ts=from_ts, to_ts=to_ts,
    )
    total = await repo.count_audit(
        action_prefix=action, user_id=user_id, from_ts=from_ts, to_ts=to_ts,
    )
    response.headers["X-Total-Count"] = str(total)
    return [AuditOut.model_validate(row) for row in rows]
```

CORS exposure: ensure FastAPI exposes `X-Total-Count` to the SPA. Since the SPA is served same-origin (mount on the same FastAPI app), no CORS headers required.

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/audit.py app_v4/tests/test_audit_api.py
git commit -m "feat(audit): action/user/date filters and total-count header"
```

---

## Task 3: AuthProvider logout + 401 interceptor

**Files:**
- Modify: `app_v4/web/src/auth/AuthProvider.tsx`
- Modify: `app_v4/web/src/api/client.ts`
- Modify: `app_v4/web/src/api/client.test.ts`

- [ ] **Step 1: Write failing test (interceptor)**

Append to `app_v4/web/src/api/client.test.ts`:

```ts
it('invokes onUnauthorized when a 401 is returned', async () => {
  const onUnauth = vi.fn();
  const detach = attachAuthInterceptor(onUnauth);
  const mock = new MockAdapter(api as unknown as AxiosInstance);
  mock.onGet('/test').reply(401);
  await expect(api.get('/test')).rejects.toBeDefined();
  expect(onUnauth).toHaveBeenCalled();
  detach();
});
```

- [ ] **Step 2: Run, FAIL** (because either interceptor missing or not wired).

- [ ] **Step 3: Confirm `attachAuthInterceptor` exists; if not, add it**

Read `app_v4/web/src/api/client.ts` first. Make sure it exports something like:

```ts
export function attachAuthInterceptor(onUnauthorized: () => void): () => void {
  const id = api.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error?.response?.status === 401) {
        onUnauthorized();
      }
      return Promise.reject(error);
    },
  );
  return () => api.interceptors.response.eject(id);
}
```

- [ ] **Step 4: AuthProvider logout test**

Create `app_v4/web/src/auth/AuthProvider.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import MockAdapter from 'axios-mock-adapter';
import type { AxiosInstance } from 'axios';
import { Router } from 'wouter';
import { memoryLocation } from 'wouter/memory-location';
import { api } from '../api/client';
import { AuthProvider, useAuth } from './AuthProvider';

function Probe({ onReady }: { onReady: (auth: ReturnType<typeof useAuth>) => void }) {
  const auth = useAuth();
  onReady(auth);
  return <span>{auth.user ? 'in' : 'out'}</span>;
}

describe('AuthProvider.logout', () => {
  it('calls /auth/logout, clears tokens, and redirects to /login', async () => {
    const mock = new MockAdapter(api as unknown as AxiosInstance);
    mock.onPost('/auth/logout').reply(204);

    let captured: ReturnType<typeof useAuth> | null = null;
    const { hook, history } = memoryLocation({ path: '/dashboard', record: true });

    render(
      <Router hook={hook}>
        <AuthProvider initialAccessToken="seeded-access" initialRefreshToken="seeded-refresh">
          <Probe onReady={(a) => { captured = a; }} />
        </AuthProvider>
      </Router>,
    );

    await act(async () => { await captured!.logout(); });

    expect(mock.history.post.find((r) => r.url === '/auth/logout')).toBeTruthy();
    expect(captured!.accessToken).toBeNull();
    expect(captured!.refreshToken).toBeNull();
    expect(history.at(-1)).toBe('/login');
    expect(screen.getByText('out')).toBeInTheDocument();
  });
});
```

If `AuthProvider` does not yet accept `initialAccessToken` / `initialRefreshToken` test props, add minimal optional constructor props that pre-seed state — these props exist *only* to make the test setup deterministic.

- [ ] **Step 5: Run, FAIL.**

- [ ] **Step 6: Implement `logout()` in AuthProvider**

Read current `AuthProvider.tsx`. Add to the context value:

```ts
const logout = async () => {
  if (refreshToken) {
    try { await api.post('/auth/logout', { refresh_token: refreshToken }); } catch { /* ignore */ }
  }
  setAccessToken(null);
  setRefreshToken(null);
  setUser(null);
  setAccessTokenInClient(null);
  setLocation('/login');
};
```

(Function names match what's currently in the file; adapt as needed.) Wire `attachAuthInterceptor(logout)` once in a `useEffect`.

- [ ] **Step 7: Run all auth/login/api tests, PASS.**

- [ ] **Step 8: Commit**

```bash
git add app_v4/web/src/auth/AuthProvider.tsx app_v4/web/src/api/client.ts app_v4/web/src/api/client.test.ts
git commit -m "feat(auth): logout action and 401 auto-logout interceptor"
```

---

## Task 4: Sidebar logout button + admin-only Activity link

**Files:**
- Modify: `app_v4/web/src/layout/Sidebar.tsx`
- Modify: `app_v4/web/src/layout/Sidebar.test.tsx`

- [ ] **Step 1: Write failing tests**

Append to `app_v4/web/src/layout/Sidebar.test.tsx`:

```tsx
import { afterEach } from 'vitest';

afterEach(() => vi.resetModules());

it('shows a Sign out button that triggers auth.logout', async () => {
  const logout = vi.fn();
  vi.doMock('../auth/AuthProvider', () => ({
    useAuth: () => ({ user: { id: 1, username: 'admin', role: 'admin', is_active: true }, logout }),
  }));
  vi.doMock('../api/hooks', () => ({
    useSystemMetrics: () => ({ data: { switches: 0, backups: 0, jobs: 0, failures_24h: 0 }, isLoading: false }),
  }));
  vi.doMock('wouter', async () => {
    const actual = await vi.importActual<typeof import('wouter')>('wouter');
    return { ...actual, useLocation: () => ['/'] };
  });

  const { Sidebar } = await import('./Sidebar');
  const user = userEvent.setup();
  render(<Sidebar />);
  await user.click(screen.getByRole('button', { name: /sign out/i }));
  expect(logout).toHaveBeenCalled();
});

it('hides the Activity link for non-admin users', async () => {
  vi.doMock('../auth/AuthProvider', () => ({
    useAuth: () => ({ user: { id: 1, username: 'op', role: 'operator', is_active: true }, logout: vi.fn() }),
  }));
  vi.doMock('../api/hooks', () => ({
    useSystemMetrics: () => ({ data: { switches: 0, backups: 0, jobs: 0, failures_24h: 0 }, isLoading: false }),
  }));
  vi.doMock('wouter', async () => {
    const actual = await vi.importActual<typeof import('wouter')>('wouter');
    return { ...actual, useLocation: () => ['/'] };
  });

  const { Sidebar } = await import('./Sidebar');
  render(<Sidebar />);
  expect(screen.queryByText(/^Activity$/)).toBeNull();
});
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Update Sidebar**

Add at the bottom of the navigation list (admin only):

```tsx
const auth = useAuth();
const role = auth.user?.role;
...
{role === 'admin' && (
  <Link href="/audit" className="nav-item">
    <span>Activity</span>
  </Link>
)}
...
<footer className="sidebar-footer">
  <span className="user-chip"><span className="dot ok" /> {auth.user?.username ?? 'admin'}</span>
  <button className="sign-out" onClick={() => auth.logout()}>Sign out ↗</button>
</footer>
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/web/src/layout/Sidebar.tsx app_v4/web/src/layout/Sidebar.test.tsx
git commit -m "feat(layout): sidebar sign-out button and admin Activity link"
```

---

## Task 5: AuditPage at `/audit`

**Files:**
- Create: `app_v4/web/src/pages/AuditPage.tsx`
- Create: `app_v4/web/src/pages/AuditPage.test.tsx`
- Modify: `app_v4/web/src/api/hooks.ts`
- Modify: `app_v4/web/src/api/types.ts`
- Modify: `app_v4/web/src/App.tsx` (add route)

- [ ] **Step 1: Add types**

```ts
export interface AuditEntry {
  id: number;
  user_id: number | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  ip: string | null;
  ts: string;
  detail_json: Record<string, unknown> | null;
}

export interface AuditFilters {
  action?: string;
  user_id?: number;
  from_ts?: string;
  to_ts?: string;
  limit?: number;
  offset?: number;
}

export interface AuditPage {
  rows: AuditEntry[];
  total: number;
}
```

- [ ] **Step 2: Add hook**

```ts
export function useAudit(filters: AuditFilters) {
  return useQuery({
    queryKey: ['audit', filters],
    queryFn: async () => {
      const response = await api.get<AuditEntry[]>('/audit', { params: filters });
      const total = Number(response.headers['x-total-count'] ?? response.data.length);
      return { rows: response.data, total };
    },
    staleTime: 30 * SECOND,
  });
}
```

- [ ] **Step 3: Write failing tests**

Create `app_v4/web/src/pages/AuditPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuditPage } from './AuditPage';

const useAuditMock = vi.fn(() => ({
  data: {
    rows: [
      { id: 1, user_id: 1, action: 'auth.login_success', target_type: null, target_id: null,
        ip: '127.0.0.1', ts: '2026-05-20T01:00:00Z', detail_json: { client: 'desktop' } },
      { id: 2, user_id: 1, action: 'switch.created', target_type: 'switch', target_id: '5',
        ip: '127.0.0.1', ts: '2026-05-20T01:01:00Z', detail_json: null },
    ],
    total: 100,
  },
  isLoading: false,
}));

vi.mock('../api/hooks', () => ({ useAudit: (filters: unknown) => useAuditMock(filters as never) }));

describe('AuditPage', () => {
  it('renders rows from useAudit', () => {
    render(<AuditPage />);
    expect(screen.getByText('auth.login_success')).toBeInTheDocument();
    expect(screen.getByText('switch.created')).toBeInTheDocument();
  });

  it('changing action group dropdown updates filter prefix', async () => {
    const user = userEvent.setup();
    useAuditMock.mockClear();
    render(<AuditPage />);
    await user.selectOptions(screen.getByLabelText(/action/i), 'auth.');
    const lastFilters = useAuditMock.mock.calls.at(-1)![0] as { action?: string };
    expect(lastFilters.action).toBe('auth.');
  });

  it('Load more increases the limit', async () => {
    const user = userEvent.setup();
    useAuditMock.mockClear();
    render(<AuditPage />);
    await user.click(screen.getByRole('button', { name: /load .* more/i }));
    const lastFilters = useAuditMock.mock.calls.at(-1)![0] as { limit?: number };
    expect(lastFilters.limit).toBeGreaterThan(50);
  });

  it('toggles detail JSON panel', async () => {
    const user = userEvent.setup();
    render(<AuditPage />);
    await user.click(screen.getByRole('button', { name: /view json/i }));
    expect(screen.getByText(/"client": "desktop"/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run, FAIL.**

- [ ] **Step 5: Implement page**

```tsx
import { useState } from 'react';
import { useAudit } from '../api/hooks';
import type { AuditFilters } from '../api/types';

const ACTION_GROUPS: Record<string, string> = {
  All: '',
  Auth: 'auth.',
  Switch: 'switch.',
  Credential: 'credential.',
  Schedule: 'schedule.',
  User: 'user.',
  Backup: 'backup.',
  System: 'system.',
};

export function AuditPage() {
  const [filters, setFilters] = useState<AuditFilters>({ limit: 50, offset: 0 });
  const [expanded, setExpanded] = useState<number | null>(null);
  const { data } = useAudit(filters);
  const rows = data?.rows ?? [];
  const total = data?.total ?? 0;

  return (
    <main>
      <p className="marker">/AUDIT</p>
      <h1 className="headline">Activity ledger.</h1>

      <section className="filter-bar">
        <label>
          Action
          <select onChange={(e) => setFilters({ ...filters, action: e.target.value || undefined, offset: 0 })}>
            {Object.entries(ACTION_GROUPS).map(([label, prefix]) => (
              <option key={label} value={prefix}>{label}</option>
            ))}
          </select>
        </label>
      </section>

      <table className="data-table">
        <thead>
          <tr><th>Time</th><th>User</th><th>Action</th><th>Target</th><th>IP</th><th>Detail</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.ts).toLocaleString()}</td>
              <td>{row.user_id ?? 'system'}</td>
              <td><span className={`badge action-${row.action.split('.')[0]}`}>{row.action}</span></td>
              <td>{row.target_type ? `${row.target_type}:${row.target_id}` : '—'}</td>
              <td>{row.ip ?? '—'}</td>
              <td>
                {row.detail_json ? (
                  <button onClick={() => setExpanded(expanded === row.id ? null : row.id)}>
                    {expanded === row.id ? 'Hide' : 'View JSON'}
                  </button>
                ) : '—'}
                {expanded === row.id && (
                  <pre className="audit-detail">{JSON.stringify(row.detail_json, null, 2)}</pre>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <footer className="audit-footer">
        <span>{rows.length} of {total}</span>
        {rows.length < total && (
          <button onClick={() => setFilters({ ...filters, limit: (filters.limit ?? 50) + 50 })}>
            Load 50 more
          </button>
        )}
      </footer>
    </main>
  );
}
```

- [ ] **Step 6: Wire route**

Edit `app_v4/web/src/App.tsx`. Add:

```tsx
<Route path="/audit"><ProtectedRoute roles={['admin']}><AuditPage /></ProtectedRoute></Route>
```

If `ProtectedRoute` doesn't yet accept `roles`, extend it to do so:

```tsx
export function ProtectedRoute({ children, roles }: { children: React.ReactNode; roles?: Role[] }) {
  const auth = useAuth();
  if (!auth.user) return <LoginPage />;
  if (roles && !roles.includes(auth.user.role)) return <p>Not authorized.</p>;
  return <>{children}</>;
}
```

- [ ] **Step 7: Run, PASS.**

Run: `npm --prefix app_v4/web test -- --run src/pages/AuditPage.test.tsx`

- [ ] **Step 8: Commit**

```bash
git add app_v4/web/src/pages/AuditPage.tsx app_v4/web/src/pages/AuditPage.test.tsx \
        app_v4/web/src/api/hooks.ts app_v4/web/src/api/types.ts \
        app_v4/web/src/auth/ProtectedRoute.tsx app_v4/web/src/App.tsx
git commit -m "feat(audit): admin audit page with filters and pagination"
```

---

## Task 6: Verify + bundle

- [ ] Run full backend `pytest`, full frontend `vitest`, `vite build`, `installer/v4/build_app.ps1 -SkipWebBuild`. All green.
