# Phase 5 — History + Diff Polish

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make History page a usable workflow tool (filters + view/download/delete) and Diff page user-friendly (switch + backup pickers instead of raw IDs).

**Architecture:**
- Backend: extend `GET /backups` with filter params; `GET /backups/{id}/content?download=true` adds Content-Disposition; `DELETE /backups/{id}` admin-only deletes DB row + file.
- Frontend: HistoryPage filter bar, view/download/delete actions, modal for view; DiffPage rebuilt with three pickers (switch / backup A / backup B).

**Tech Stack:** FastAPI, SQLAlchemy, React Query, Wouter, vitest, pytest.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 5.

---

## Task 1: Repository extension for filtered backup list

**Files:**
- Modify: `app_v4/data/repository.py`
- Modify: `app_v4/tests/test_repository.py`

- [ ] **Step 1: Write failing test**

Append to `app_v4/tests/test_repository.py`:

```python
@pytest.mark.asyncio
async def test_list_backups_filters_by_success_type_q_and_date(session_factory, seeded_switch_id):
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_backup(switch_id=seeded_switch_id, file_path="", content_hash="x", size_bytes=10,
                                  success=True, message="ok manual", backup_type="manual")
        await repo.create_backup(switch_id=seeded_switch_id, file_path="", content_hash="y", size_bytes=20,
                                  success=False, message="timeout", backup_type="automatic")
        await session.commit()

    async with session_factory() as session:
        repo = Repository(session)
        success_only = await repo.list_backups(switch_id=seeded_switch_id, success=True)
        failed_only = await repo.list_backups(switch_id=seeded_switch_id, success=False)
        manual_only = await repo.list_backups(switch_id=seeded_switch_id, backup_type="manual")
        searched = await repo.list_backups(switch_id=seeded_switch_id, q="time")

    assert len(success_only) == 1 and success_only[0].success is True
    assert len(failed_only) == 1 and failed_only[0].success is False
    assert len(manual_only) == 1 and manual_only[0].backup_type == "manual"
    assert len(searched) == 1 and "time" in (searched[0].message or "")
```

- [ ] **Step 2: Run, FAIL.**

Run: `python -m pytest app_v4/tests/test_repository.py -v`

- [ ] **Step 3: Extend `Repository.list_backups`**

Edit `app_v4/data/repository.py`:

```python
async def list_backups(
    self,
    switch_id: int | None = None,
    limit: int = 100,
    success: bool | None = None,
    backup_type: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    q: str | None = None,
) -> list[Backup]:
    stmt = select(Backup).order_by(Backup.taken_at.desc()).limit(limit)
    if switch_id is not None:
        stmt = stmt.where(Backup.switch_id == switch_id)
    if success is not None:
        stmt = stmt.where(Backup.success.is_(success))
    if backup_type is not None:
        stmt = stmt.where(Backup.backup_type == backup_type)
    if from_ts is not None:
        stmt = stmt.where(Backup.taken_at >= from_ts)
    if to_ts is not None:
        stmt = stmt.where(Backup.taken_at <= to_ts)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Backup.message.ilike(like))
    result = await self.session.execute(stmt)
    return list(result.scalars().all())
```

Make sure `from sqlalchemy import select` and `datetime` are already imported.

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/data/repository.py app_v4/tests/test_repository.py
git commit -m "feat(repository): list_backups gains filter params"
```

---

## Task 2: API filters + delete + download header

**Files:**
- Modify: `app_v4/service/api/backups.py`
- Modify: `app_v4/tests/test_backups_api.py`

- [ ] **Step 1: Write failing tests**

Append to `app_v4/tests/test_backups_api.py`:

```python
@pytest.mark.asyncio
async def test_list_backups_filters(client, viewer_token, seeded_two_backups):
    r = await client.get(
        "/api/v1/backups?success=true",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r.status_code == 200
    assert all(b["success"] for b in r.json())


@pytest.mark.asyncio
async def test_download_backup_content_sets_content_disposition(client, viewer_token, seeded_backup_id):
    r = await client.get(
        f"/api/v1/backups/{seeded_backup_id}/content?download=true",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r.status_code == 200
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".txt" in cd


@pytest.mark.asyncio
async def test_delete_backup_admin_only_removes_row_and_file(client, admin_token, operator_token, seeded_backup_with_file):
    backup_id, file_path = seeded_backup_with_file
    r = await client.delete(
        f"/api/v1/backups/{backup_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert r.status_code == 403

    r = await client.delete(
        f"/api/v1/backups/{backup_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204
    from pathlib import Path
    assert not Path(file_path).exists()

    r = await client.get(f"/api/v1/backups/{backup_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 404
```

If the fixtures aren't there, add them in `conftest.py` following existing patterns.

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Extend `list_backups` query params + content download + delete**

Edit `app_v4/service/api/backups.py`. Update `list_backups`:

```python
@router.get("/backups", response_model=list[BackupOut])
async def list_backups(
    switch_id: int | None = None,
    limit: int = 100,
    success: bool | None = None,
    backup_type: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[BackupOut]:
    repo = Repository(session)
    rows = await repo.list_backups(
        switch_id=switch_id, limit=limit, success=success, backup_type=backup_type,
        from_ts=from_ts, to_ts=to_ts, q=q,
    )
    return [_to_out(b) for b in rows]
```

Update content endpoint to support `download` flag:

```python
@router.get("/backups/{backup_id}/content")
async def get_backup_content(
    backup_id: int,
    download: bool = False,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> Response:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    path = Path(backup.file_path)
    if not path.exists():
        raise problem(404, "Not Found", "Backup file not found")
    text = path.read_text(encoding="utf-8")
    headers = {}
    if download:
        switch = await repo.get_switch(backup.switch_id)
        switch_name = switch.name if switch else f"switch-{backup.switch_id}"
        ts = backup.taken_at.strftime("%Y%m%d-%H%M%S")
        filename = f"{switch_name}_{ts}.txt"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(text, media_type="text/plain", headers=headers)
```

Add delete endpoint:

```python
@router.delete("/backups/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backup(
    backup_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    user: AccessClaims = Depends(require_role("admin")),
) -> Response:
    repo = Repository(session)
    backup = await repo.get_backup(backup_id)
    if backup is None:
        raise problem(404, "Not Found", "Backup not found")
    file_path = backup.file_path
    await repo.delete_backup(backup_id)
    await session.commit()
    if file_path:
        Path(file_path).unlink(missing_ok=True)
    await runtime.audit_writer.record(
        action="backup.deleted",
        user_id=user.user_id,
        target_type="backup",
        target_id=str(backup_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

If `Repository.delete_backup` doesn't exist, add:

```python
async def delete_backup(self, backup_id: int) -> None:
    backup = await self.get_backup(backup_id)
    if backup is not None:
        await self.session.delete(backup)
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/backups.py app_v4/data/repository.py app_v4/tests/test_backups_api.py
git commit -m "feat(backups): list filters, download attachment, admin delete"
```

---

## Task 3: Frontend hooks for backup actions

**Files:**
- Modify: `app_v4/web/src/api/hooks.ts`
- Modify: `app_v4/web/src/api/types.ts`

- [ ] **Step 1: Add types**

```ts
export interface BackupFilters {
  switch_id?: number;
  success?: boolean;
  backup_type?: 'manual' | 'automatic' | 'manual_schedule';
  from_ts?: string;
  to_ts?: string;
  q?: string;
}
```

- [ ] **Step 2: Add hooks**

```ts
export function useFilteredBackups(filters: BackupFilters) {
  return useQuery({
    queryKey: ['backups', 'filtered', filters],
    queryFn: async () => (await api.get<BackupRecord[]>('/backups', { params: filters })).data,
    staleTime: 15 * SECOND,
  });
}

export async function fetchBackupContent(id: number): Promise<string> {
  return (await api.get<string>(`/backups/${id}/content`, { responseType: 'text' })).data as unknown as string;
}

export function useDeleteBackup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/backups/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backups'] }),
  });
}
```

For Download, we trigger an anchor with the URL because the browser will follow the Content-Disposition header. Helper:

```ts
export function downloadBackupUrl(id: number): string {
  return `/api/v1/backups/${id}/content?download=true`;
}
```

- [ ] **Step 3: Build to type-check.**

Run: `npm --prefix app_v4/web run build`

- [ ] **Step 4: Commit**

```bash
git add app_v4/web/src/api/hooks.ts app_v4/web/src/api/types.ts
git commit -m "feat(api): backup filter, content fetch, delete hooks"
```

---

## Task 4: HistoryPage filter bar + view modal + actions

**Files:**
- Modify: `app_v4/web/src/pages/HistoryPage.tsx`
- Modify: `app_v4/web/src/pages/HistoryPage.test.tsx`
- Create: `app_v4/web/src/components/BackupViewModal.tsx`

- [ ] **Step 1: Write failing tests**

Replace `app_v4/web/src/pages/HistoryPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HistoryPage } from './HistoryPage';

const filteredFactory = vi.fn(() => ({
  data: [
    { id: 100, switch_id: 1, backup_type: 'manual', success: true,
      created_at: '2026-05-20T01:00:00Z', size_bytes: 2048, message: 'ok' },
  ],
  isLoading: false,
}));
const deleteMutate = vi.fn();

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [{ id: 1, name: 'SW-A', ip: '10.0.0.1', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true }] }),
  useFilteredBackups: (filters: unknown) => filteredFactory(filters as never),
  useDeleteBackup: () => ({ mutate: deleteMutate, isPending: false }),
  fetchBackupContent: vi.fn(async () => 'config text'),
  downloadBackupUrl: (id: number) => `/api/v1/backups/${id}/content?download=true`,
}));

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({ user: { id: 1, username: 'admin', role: 'admin', is_active: true } }),
}));

describe('HistoryPage', () => {
  it('passes selected filters to useFilteredBackups', async () => {
    const user = userEvent.setup();
    filteredFactory.mockClear();
    render(<HistoryPage />);
    await user.selectOptions(screen.getByLabelText(/state/i), 'success');
    const lastCall = filteredFactory.mock.calls.at(-1)![0] as { success?: boolean };
    expect(lastCall.success).toBe(true);
  });

  it('opens the view modal when clicking View', async () => {
    const user = userEvent.setup();
    render(<HistoryPage />);
    await user.click(screen.getByRole('button', { name: /view/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('Delete (admin) calls useDeleteBackup after confirm', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<HistoryPage />);
    await user.click(screen.getByRole('button', { name: /delete/i }));
    expect(deleteMutate).toHaveBeenCalledWith(100);
    confirm.mockRestore();
  });
});
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Create `BackupViewModal.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { fetchBackupContent } from '../api/hooks';

export function BackupViewModal({ backupId, onClose }: { backupId: number; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBackupContent(backupId).then(setText).catch((err) => setError(err.message ?? 'Failed to load'));
  }, [backupId]);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <h2>Backup #{backupId}</h2>
          <button onClick={onClose}>Close</button>
        </header>
        {error ? <p role="alert">{error}</p> : null}
        {text === null && !error ? <p>Loading…</p> : <pre>{text}</pre>}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement HistoryPage**

```tsx
import { useState } from 'react';
import {
  downloadBackupUrl,
  useDeleteBackup,
  useFilteredBackups,
  useSwitches,
} from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import { BackupViewModal } from '../components/BackupViewModal';
import type { BackupFilters } from '../api/types';

export function HistoryPage() {
  const auth = useAuth();
  const isAdmin = auth.user?.role === 'admin';
  const [filters, setFilters] = useState<BackupFilters>({});
  const [viewing, setViewing] = useState<number | null>(null);
  const { data: switches = [] } = useSwitches();
  const { data: rows = [] } = useFilteredBackups(filters);
  const remove = useDeleteBackup();

  return (
    <main>
      <p className="marker">/05 · HIST</p>
      <h1 className="headline">Every config has a trail.</h1>

      <section className="filter-bar">
        <label>
          Switch
          <select
            value={filters.switch_id ?? ''}
            onChange={(event) => setFilters({ ...filters, switch_id: event.target.value ? Number(event.target.value) : undefined })}
          >
            <option value="">All</option>
            {switches.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>
        <label>
          Type
          <select
            value={filters.backup_type ?? ''}
            onChange={(event) => setFilters({ ...filters, backup_type: (event.target.value || undefined) as BackupFilters['backup_type'] })}
          >
            <option value="">All</option>
            <option value="manual">Manual</option>
            <option value="automatic">Automatic</option>
            <option value="manual_schedule">Manual (schedule)</option>
          </select>
        </label>
        <label>
          State
          <select
            value={filters.success === undefined ? '' : filters.success ? 'success' : 'failed'}
            onChange={(event) => {
              const v = event.target.value;
              setFilters({ ...filters, success: v === '' ? undefined : v === 'success' });
            }}
          >
            <option value="">All</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
          </select>
        </label>
        <label>
          Search
          <input
            value={filters.q ?? ''}
            onChange={(event) => setFilters({ ...filters, q: event.target.value || undefined })}
          />
        </label>
      </section>

      <table className="data-table">
        <thead>
          <tr><th>Time</th><th>Switch</th><th>Type</th><th>State</th><th>Size</th><th>Message</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {rows.map((b) => {
            const switchName = switches.find((s) => s.id === b.switch_id)?.name ?? b.switch_id;
            return (
              <tr key={b.id}>
                <td>{new Date(b.created_at).toLocaleString()}</td>
                <td>{switchName}</td>
                <td><span className={`badge type-${b.backup_type}`}>{b.backup_type}</span></td>
                <td><span className={`badge state-${b.success ? 'ok' : 'fail'}`}>{b.success ? 'ok' : 'failed'}</span></td>
                <td>{b.size_bytes ? `${Math.round((b.size_bytes ?? 0) / 1024)} KB` : '—'}</td>
                <td title={b.message ?? ''}>{(b.message ?? '').slice(0, 60)}</td>
                <td className="row-actions">
                  <button onClick={() => setViewing(b.id)}>View</button>
                  <a href={downloadBackupUrl(b.id)} className="button">Download</a>
                  {isAdmin && (
                    <button onClick={() => {
                      if (window.confirm(`Delete backup #${b.id}? Backup file will be removed.`)) {
                        remove.mutate(b.id);
                      }
                    }}>Delete</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {viewing !== null && <BackupViewModal backupId={viewing} onClose={() => setViewing(null)} />}
    </main>
  );
}
```

- [ ] **Step 5: Run tests, PASS.**

Run: `npm --prefix app_v4/web test -- --run src/pages/HistoryPage.test.tsx`

- [ ] **Step 6: Commit**

```bash
git add app_v4/web/src/pages/HistoryPage.tsx app_v4/web/src/pages/HistoryPage.test.tsx app_v4/web/src/components/BackupViewModal.tsx
git commit -m "feat(history): filter bar, view modal, download, admin delete"
```

---

## Task 5: DiffPage with switch + backup pickers

**Files:**
- Modify: `app_v4/web/src/pages/DiffPage.tsx`
- Create: `app_v4/web/src/pages/DiffPage.test.tsx`

- [ ] **Step 1: Write failing test**

Create `app_v4/web/src/pages/DiffPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DiffPage } from './DiffPage';

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [
    { id: 1, name: 'SW-A', ip: '10.0.0.1', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
    { id: 2, name: 'SW-B', ip: '10.0.0.2', host: '10.0.0.2', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
  ], isLoading: false }),
  useFilteredBackups: ({ switch_id }: { switch_id: number }) => ({
    data: switch_id === 1 ? [
      { id: 30, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-20T09:00:00Z' },
      { id: 29, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-19T09:00:00Z' },
      { id: 28, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-18T09:00:00Z' },
    ] : [],
    isLoading: false,
  }),
}));

vi.mock('../api/client', () => ({
  api: { get: vi.fn(async () => ({ data: '--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n' })) },
}));

describe('DiffPage', () => {
  it('populates A and B pickers from selected switch backups and disables Compare when A === B', async () => {
    render(<DiffPage />);
    const aSelect = screen.getByLabelText(/backup a/i) as HTMLSelectElement;
    const bSelect = screen.getByLabelText(/backup b/i) as HTMLSelectElement;
    expect(aSelect.options.length).toBe(3);
    expect(bSelect.options.length).toBe(3);
    expect(aSelect.value).not.toBe(bSelect.value);

    const user = userEvent.setup();
    await user.selectOptions(aSelect, bSelect.value);
    expect(screen.getByRole('button', { name: /compare/i })).toBeDisabled();
  });

  it('clicking Compare fetches /backups/diff with both ids', async () => {
    const { api } = await import('../api/client');
    const user = userEvent.setup();
    render(<DiffPage />);
    await user.click(screen.getByRole('button', { name: /compare/i }));
    expect(api.get).toHaveBeenCalledWith('/backups/diff', expect.objectContaining({
      params: expect.objectContaining({ a: expect.any(Number), b: expect.any(Number) }),
      responseType: 'text',
    }));
  });
});
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement DiffPage**

```tsx
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useFilteredBackups, useSwitches } from '../api/hooks';

export function DiffPage() {
  const { data: switches = [] } = useSwitches();
  const [switchId, setSwitchId] = useState<number | null>(null);
  const { data: backups = [] } = useFilteredBackups(switchId ? { switch_id: switchId } : { switch_id: -1 });
  const [aId, setAId] = useState<number | null>(null);
  const [bId, setBId] = useState<number | null>(null);
  const [diff, setDiff] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (switches.length > 0 && switchId === null) setSwitchId(switches[0].id);
  }, [switches, switchId]);

  useEffect(() => {
    if (backups.length >= 2) {
      setAId(backups[1].id);
      setBId(backups[0].id);
    } else {
      setAId(null);
      setBId(null);
    }
  }, [backups]);

  async function compare() {
    if (aId === null || bId === null) return;
    setError(null);
    try {
      const response = await api.get('/backups/diff', { params: { a: aId, b: bId }, responseType: 'text' });
      setDiff(response.data as string);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load diff');
    }
  }

  const enoughBackups = backups.length >= 2;

  return (
    <main>
      <p className="marker">/06 · DIFF</p>
      <h1 className="headline">Diffs expose drift.</h1>

      <section className="filter-bar">
        <label>
          Switch
          <select value={switchId ?? ''} onChange={(e) => setSwitchId(Number(e.target.value))}>
            {switches.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label>
          Backup A
          <select value={aId ?? ''} disabled={!enoughBackups} onChange={(e) => setAId(Number(e.target.value))}>
            {backups.map((b) => <option key={b.id} value={b.id}>#{b.id} — {new Date(b.created_at).toLocaleString()}</option>)}
          </select>
        </label>
        <label>
          Backup B
          <select value={bId ?? ''} disabled={!enoughBackups} onChange={(e) => setBId(Number(e.target.value))}>
            {backups.map((b) => <option key={b.id} value={b.id}>#{b.id} — {new Date(b.created_at).toLocaleString()}</option>)}
          </select>
        </label>
        <button onClick={compare} disabled={!enoughBackups || aId === bId}>
          Compare
        </button>
      </section>

      {!enoughBackups && switchId !== null ? <p>Need at least 2 backups to compare.</p> : null}
      {error ? <div role="alert">{error}</div> : null}
      <pre className="diff-output">{diff}</pre>
    </main>
  );
}
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/web/src/pages/DiffPage.tsx app_v4/web/src/pages/DiffPage.test.tsx
git commit -m "feat(diff): switch and backup pickers replace raw ID input"
```

---

## Task 6: Verify + bundle rebuild

- [ ] Run full backend `pytest`, full frontend `vitest`, `vite build`, `installer/v4/build_app.ps1 -SkipWebBuild`. Each step must succeed before proceeding.
