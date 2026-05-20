# Phase 3 — CRUD Switch + Credential (inline, hybrid, soft delete)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inline Add/Edit/Deactivate/Activate/Delete UX for switches and credentials. Soft delete (deactivate first, hard delete only when inactive). Hybrid credential combobox lets users pick existing or create new during switch creation.

**Architecture:**
- Backend: schema migration adds `Switch.is_active`, `Switch.deactivated_at`. New endpoints `POST /switches/{id}/deactivate`, `POST /switches/{id}/activate`. `DELETE /switches/{id}` returns 409 if active. `GET /switches` filters active by default; `?include_inactive=true` opts in.
- Scheduler skips inactive switches (`sync_once`).
- Manual backup on inactive switch returns 409.
- Frontend: SwitchesPage + CredentialsPage gain inline editing rows + action menu. New mutation hooks. Hybrid combobox.

**Tech Stack:** SQLAlchemy 2 async, FastAPI, Pydantic v2, React Query, vitest, pytest.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 3.

---

## Task 1: Schema migration for `is_active` + `deactivated_at`

**Files:**
- Modify: `app_v4/data/models.py`
- Modify: `app_v4/data/db.py`
- Modify: `app_v4/tests/test_db_init.py`

- [ ] **Step 1: Write failing test**

Append to `app_v4/tests/test_db_init.py`:

```python
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app_v4.data.db import init_db
from app_v4.data.models import Base


@pytest.mark.asyncio
async def test_switches_table_has_is_active_and_deactivated_at(tmp_path):
    db_url = f"sqlite+aiosqlite:///{(tmp_path / 'app.db').as_posix()}"
    engine = create_async_engine(db_url)
    await init_db(engine)
    async with engine.begin() as conn:
        cols = await conn.run_sync(lambda sync_conn: {c['name'] for c in inspect(sync_conn).get_columns('switches')})
    assert 'is_active' in cols
    assert 'deactivated_at' in cols
```

- [ ] **Step 2: Run test to verify FAIL**

Run: `python -m pytest app_v4/tests/test_db_init.py -v`
Expected: FAIL — columns don't exist yet.

- [ ] **Step 3: Add columns to model**

Edit `app_v4/data/models.py`. In class `Switch`, after `notes`, add:

```python
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Add migration helper**

Edit `app_v4/data/db.py`. In `_run_sqlite_migrations`, append:

```python
    await _add_column_if_missing(conn, "switches", "is_active", "INTEGER NOT NULL DEFAULT 1")
    await _add_column_if_missing(conn, "switches", "deactivated_at", "DATETIME")
```

- [ ] **Step 5: Run test to confirm PASS**

Run: `python -m pytest app_v4/tests/test_db_init.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app_v4/data/models.py app_v4/data/db.py app_v4/tests/test_db_init.py
git commit -m "feat(db): add is_active and deactivated_at to switches"
```

---

## Task 2: Backend deactivate/activate endpoints + delete-while-active 409

**Files:**
- Modify: `app_v4/data/repository.py`
- Modify: `app_v4/service/api/switches.py`
- Modify: `app_v4/tests/test_switches_api.py`

- [ ] **Step 1: Write failing tests**

Append to `app_v4/tests/test_switches_api.py`:

```python
@pytest.mark.asyncio
async def test_deactivate_then_delete_switch(client, admin_token, seeded_switch_id):
    r = await client.post(
        f"/api/v1/switches/{seeded_switch_id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    r = await client.delete(
        f"/api/v1/switches/{seeded_switch_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_active_switch_returns_409(client, admin_token, seeded_switch_id):
    r = await client.delete(
        f"/api/v1/switches/{seeded_switch_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 409
    assert "deactivate" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_switches_excludes_inactive_by_default(client, admin_token, seeded_switch_id):
    await client.post(
        f"/api/v1/switches/{seeded_switch_id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = await client.get("/api/v1/switches", headers={"Authorization": f"Bearer {admin_token}"})
    assert all(sw["id"] != seeded_switch_id for sw in r.json())

    r = await client.get(
        "/api/v1/switches?include_inactive=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert any(sw["id"] == seeded_switch_id for sw in r.json())


@pytest.mark.asyncio
async def test_activate_switch(client, admin_token, seeded_switch_id):
    await client.post(
        f"/api/v1/switches/{seeded_switch_id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = await client.post(
        f"/api/v1/switches/{seeded_switch_id}/activate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204
    r = await client.get("/api/v1/switches", headers={"Authorization": f"Bearer {admin_token}"})
    assert any(sw["id"] == seeded_switch_id for sw in r.json())
```

If `seeded_switch_id` fixture doesn't exist in `conftest.py`, add one that creates a switch + credential. Read `app_v4/tests/conftest.py` first to see existing fixtures and follow its patterns.

- [ ] **Step 2: Run tests, expect FAIL**

Run: `python -m pytest app_v4/tests/test_switches_api.py -v`
Expected: FAIL.

- [ ] **Step 3: Add repository methods**

Edit `app_v4/data/repository.py`. Add (or modify) methods:

```python
async def list_switches(self, include_inactive: bool = False) -> list[Switch]:
    stmt = select(Switch)
    if not include_inactive:
        stmt = stmt.where(Switch.is_active.is_(True))
    stmt = stmt.order_by(Switch.id)
    result = await self.session.execute(stmt)
    return list(result.scalars().all())

async def deactivate_switch(self, switch_id: int) -> Switch | None:
    switch = await self.get_switch(switch_id)
    if switch is None:
        return None
    switch.is_active = False
    switch.deactivated_at = datetime.utcnow()
    return switch

async def activate_switch(self, switch_id: int) -> Switch | None:
    switch = await self.get_switch(switch_id)
    if switch is None:
        return None
    switch.is_active = True
    switch.deactivated_at = None
    return switch
```

- [ ] **Step 4: Update API**

Edit `app_v4/service/api/switches.py`. Modify list endpoint to accept `include_inactive`, add deactivate/activate, change delete to enforce inactive:

```python
@router.get("/switches", response_model=list[SwitchOut])
async def list_switches(
    include_inactive: bool = False,
    session: AsyncSession = Depends(get_db),
    _user: AccessClaims = Depends(require_role("admin", "operator", "viewer")),
) -> list[SwitchOut]:
    repo = Repository(session)
    return [_to_out(s) for s in await repo.list_switches(include_inactive=include_inactive)]


@router.post("/switches/{switch_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_switch(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    user: AccessClaims = Depends(require_role("admin", "operator")),
) -> Response:
    repo = Repository(session)
    switch = await repo.deactivate_switch(switch_id)
    if switch is None:
        raise problem(404, "Not Found", "Switch not found")
    await session.commit()
    await runtime.audit_writer.record(
        action="switch.deactivated",
        user_id=user.user_id,
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/switches/{switch_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
async def activate_switch(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    user: AccessClaims = Depends(require_role("admin", "operator")),
) -> Response:
    repo = Repository(session)
    switch = await repo.activate_switch(switch_id)
    if switch is None:
        raise problem(404, "Not Found", "Switch not found")
    await session.commit()
    await runtime.audit_writer.record(
        action="switch.activated",
        user_id=user.user_id,
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/switches/{switch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_switch(
    switch_id: int,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    session: AsyncSession = Depends(get_db),
    user: AccessClaims = Depends(require_role("admin")),
) -> Response:
    repo = Repository(session)
    switch = await repo.get_switch(switch_id)
    if switch is None:
        raise problem(404, "Not Found", "Switch not found")
    if switch.is_active:
        raise problem(409, "Conflict", "Switch must be deactivated before delete")
    await repo.delete_switch(switch_id)
    await session.commit()
    await runtime.audit_writer.record(
        action="switch.deleted",
        user_id=user.user_id,
        target_type="switch",
        target_id=str(switch_id),
        ip=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

`SwitchOut` schema needs `is_active: bool` and `deactivated_at: datetime | None`. Add them.

- [ ] **Step 5: Run tests to confirm PASS**

Run: `python -m pytest app_v4/tests/test_switches_api.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app_v4/data/repository.py app_v4/service/api/switches.py app_v4/tests/test_switches_api.py
git commit -m "feat(switches): soft delete (deactivate/activate) endpoints"
```

---

## Task 3: Scheduler + manual backup respect inactive

**Files:**
- Modify: `app_v4/service/scheduler.py`
- Modify: `app_v4/service/backup_service.py`
- Modify: `app_v4/tests/test_scheduler.py`
- Modify: `app_v4/tests/test_backup_service.py`

- [ ] **Step 1: Write failing tests**

Append to `app_v4/tests/test_scheduler.py`:

```python
@pytest.mark.asyncio
async def test_scheduler_skips_jobs_for_inactive_switches(scheduler_setup):
    # use existing scheduler_setup fixture; deactivate the switch and assert sync_once removes the job
    ...
```

Append to `app_v4/tests/test_backup_service.py`:

```python
@pytest.mark.asyncio
async def test_manual_backup_blocked_for_inactive_switch(backup_service, seeded_switch_id, session_factory):
    async with session_factory() as session:
        from app_v4.data.repository import Repository
        await Repository(session).deactivate_switch(seeded_switch_id)
        await session.commit()
    with pytest.raises(ValueError, match="inactive"):
        await backup_service.execute_backup(seeded_switch_id)
```

Read existing fixtures in `conftest.py` to use the right ones.

- [ ] **Step 2: Run tests, expect FAIL.**

- [ ] **Step 3: Implement skip in `scheduler.py:sync_once`**

Modify the loop:
```python
for job in jobs:
    if not job.enabled:
        continue
    switch = await repo.get_switch(job.switch_id)
    if switch is None or not switch.is_active:
        if job.id in self.job_map:
            self.remove_job(job.id)
        continue
    ...
```

- [ ] **Step 4: Implement check in `backup_service.execute_backup`**

After loading switch, before publishing event:
```python
if not switch.is_active:
    raise ValueError(f"Switch {switch_id} is inactive")
```

`backups.py` API already wraps `ValueError` to 404; change wrapper to detect "inactive" message and surface 409 instead. Or raise a typed exception. Simplest: catch `ValueError` in API, if message contains "inactive" return 409.

- [ ] **Step 5: Run tests to confirm PASS, then full suite.**

Run: `python -m pytest app_v4/tests/ -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add app_v4/service/scheduler.py app_v4/service/backup_service.py \
        app_v4/service/api/backups.py app_v4/tests/test_scheduler.py app_v4/tests/test_backup_service.py
git commit -m "feat(scheduler): skip inactive switches; manual backup blocked"
```

---

## Task 4: Frontend mutation hooks

**Files:**
- Modify: `app_v4/web/src/api/hooks.ts`
- Modify: `app_v4/web/src/api/types.ts`

- [ ] **Step 1: Add typed payloads to `types.ts`**

Append:

```ts
export interface SwitchCreateInput {
  name: string;
  ip: string;
  protocol: string;
  port: number;
  credential_id: number;
  notes?: string | null;
}

export interface SwitchUpdateInput extends Partial<SwitchCreateInput> {
  is_active?: boolean;
}

export interface CredentialCreateInput {
  name: string;
  username: string;
  password: string;
  enable_password?: string;
}

export type CredentialUpdateInput = Partial<CredentialCreateInput>;
```

- [ ] **Step 2: Add hooks**

Append to `app_v4/web/src/api/hooks.ts`:

```ts
export function useCreateSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: SwitchCreateInput) => (await api.post<SwitchRecord>('/switches', input)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['switches'] });
      qc.invalidateQueries({ queryKey: ['system', 'metrics'] });
    },
  });
}

export function useUpdateSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: number; input: SwitchUpdateInput }) =>
      (await api.patch<SwitchRecord>(`/switches/${vars.id}`, vars.input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['switches'] }),
  });
}

export function useDeactivateSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.post(`/switches/${id}/deactivate`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['switches'] }),
  });
}

export function useActivateSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.post(`/switches/${id}/activate`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['switches'] }),
  });
}

export function useDeleteSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/switches/${id}`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['switches'] });
      qc.invalidateQueries({ queryKey: ['system', 'metrics'] });
    },
  });
}

export function useCreateCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: CredentialCreateInput) =>
      (await api.post<CredentialRecord>('/credentials', input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
}

export function useUpdateCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: number; input: CredentialUpdateInput }) =>
      (await api.patch<CredentialRecord>(`/credentials/${vars.id}`, vars.input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
}

export function useDeleteCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/credentials/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credentials'] }),
  });
}
```

Also add `import` for the new types at the top of `hooks.ts`:
```ts
import type { ..., SwitchCreateInput, SwitchUpdateInput, CredentialCreateInput, CredentialUpdateInput } from './types';
```

- [ ] **Step 3: Type-check**

Run: `npm --prefix app_v4/web run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add app_v4/web/src/api/hooks.ts app_v4/web/src/api/types.ts
git commit -m "feat(api): mutation hooks for switch and credential CRUD"
```

---

## Task 5: `CredentialCombo` component (hybrid select-or-create)

**Files:**
- Create: `app_v4/web/src/components/CredentialCombo.tsx`
- Create: `app_v4/web/src/components/CredentialCombo.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CredentialCombo } from './CredentialCombo';

const credentials = [
  { id: 1, name: 'Lab admin' },
  { id: 2, name: 'Datacenter ops' },
];

describe('CredentialCombo', () => {
  it('selects an existing credential', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<CredentialCombo credentials={credentials} value={null} onChange={onChange} onCreateNew={vi.fn()} />);
    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByRole('option', { name: 'Lab admin' }));
    expect(onChange).toHaveBeenCalledWith(1);
  });

  it('triggers onCreateNew when "+ New credential" picked', async () => {
    const user = userEvent.setup();
    const onCreateNew = vi.fn();
    render(<CredentialCombo credentials={credentials} value={null} onChange={vi.fn()} onCreateNew={onCreateNew} />);
    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByRole('option', { name: /\+ new credential/i }));
    expect(onCreateNew).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test, expect FAIL.**

- [ ] **Step 3: Implement combo (no extra dependency, plain `<select>` + sentinel)**

Create `app_v4/web/src/components/CredentialCombo.tsx`:

```tsx
import type { CredentialRecord } from '../api/types';

const NEW_SENTINEL = '__new__';

export function CredentialCombo({
  credentials,
  value,
  onChange,
  onCreateNew,
}: {
  credentials: CredentialRecord[];
  value: number | null;
  onChange: (id: number) => void;
  onCreateNew: () => void;
}) {
  return (
    <select
      role="combobox"
      value={value === null ? '' : String(value)}
      onChange={(event) => {
        const v = event.target.value;
        if (v === NEW_SENTINEL) {
          onCreateNew();
        } else if (v !== '') {
          onChange(Number(v));
        }
      }}
    >
      <option value="" disabled>
        Select credential…
      </option>
      {credentials.map((c) => (
        <option key={c.id} value={c.id}>
          {c.name}
        </option>
      ))}
      <option value={NEW_SENTINEL}>+ New credential</option>
    </select>
  );
}
```

- [ ] **Step 4: Run test, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/web/src/components/CredentialCombo.tsx app_v4/web/src/components/CredentialCombo.test.tsx
git commit -m "feat(switches): credential combobox (select existing or create new)"
```

---

## Task 6: SwitchesPage inline CRUD

**Files:**
- Modify: `app_v4/web/src/pages/SwitchesPage.tsx`
- Modify: `app_v4/web/src/pages/SwitchesPage.test.tsx`

- [ ] **Step 1: Write failing tests**

Replace `SwitchesPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SwitchesPage } from './SwitchesPage';

const createMutate = vi.fn();
const deactivateMutate = vi.fn();

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [
    { id: 1, name: 'SW-CORE-01', ip: '10.0.0.1', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
    { id: 2, name: 'SW-OLD-01', ip: '10.0.0.99', host: '10.0.0.99', protocol: 'telnet', port: 23, credential_id: 1, is_active: false },
  ], isLoading: false }),
  useCredentials: () => ({ data: [{ id: 1, name: 'Lab admin' }], isLoading: false }),
  useTriggerBackup: () => ({ mutate: vi.fn() }),
  useCreateSwitch: () => ({ mutate: createMutate, isPending: false }),
  useUpdateSwitch: () => ({ mutate: vi.fn(), isPending: false }),
  useDeactivateSwitch: () => ({ mutate: deactivateMutate, isPending: false }),
  useActivateSwitch: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteSwitch: () => ({ mutate: vi.fn(), isPending: false }),
  useCreateCredential: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

describe('SwitchesPage', () => {
  it('opens an inline add row when clicking + Add switch', async () => {
    const user = userEvent.setup();
    render(<SwitchesPage />);
    await user.click(screen.getByRole('button', { name: /add switch/i }));
    expect(screen.getByPlaceholderText(/name/i)).toBeInTheDocument();
  });

  it('hides inactive switches by default and reveals via filter', async () => {
    const user = userEvent.setup();
    render(<SwitchesPage />);
    expect(screen.queryByText('SW-OLD-01')).toBeNull();
    await user.click(screen.getByLabelText(/show inactive/i));
    expect(screen.getByText('SW-OLD-01')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test, FAIL.**

- [ ] **Step 3: Replace `SwitchesPage.tsx`**

Overwrite with the full inline-CRUD page. Key sections:

```tsx
import { useMemo, useState } from 'react';
import {
  useCreateCredential,
  useCreateSwitch,
  useCredentials,
  useDeactivateSwitch,
  useActivateSwitch,
  useDeleteSwitch,
  useSwitches,
  useTriggerBackup,
  useUpdateSwitch,
} from '../api/hooks';
import { CredentialCombo } from '../components/CredentialCombo';
import type { SwitchRecord } from '../api/types';

const PROTOCOLS = ['ssh', 'telnet', 'websmart'] as const;
const DEFAULT_PORT: Record<string, number> = { ssh: 22, telnet: 23, websmart: 443 };

interface DraftSwitch {
  id: number | null;
  name: string;
  ip: string;
  protocol: string;
  port: number;
  credential_id: number | null;
  notes: string;
}

const EMPTY: DraftSwitch = { id: null, name: '', ip: '', protocol: 'ssh', port: 22, credential_id: null, notes: '' };

export function SwitchesPage() {
  const [showInactive, setShowInactive] = useState(false);
  const [draft, setDraft] = useState<DraftSwitch | null>(null);
  const [showNewCred, setShowNewCred] = useState(false);
  const [newCred, setNewCred] = useState({ name: '', username: '', password: '', enable_password: '' });

  const { data: switches = [] } = useSwitches();
  const { data: credentials = [] } = useCredentials();
  const create = useCreateSwitch();
  const update = useUpdateSwitch();
  const deactivate = useDeactivateSwitch();
  const activate = useActivateSwitch();
  const remove = useDeleteSwitch();
  const backup = useTriggerBackup();
  const createCred = useCreateCredential();

  const visible = useMemo(
    () => (showInactive ? switches : switches.filter((s) => s.is_active)),
    [switches, showInactive],
  );

  function startAdd() {
    setDraft({ ...EMPTY });
    setShowNewCred(false);
  }
  function startEdit(sw: SwitchRecord) {
    setDraft({
      id: sw.id,
      name: sw.name,
      ip: sw.ip,
      protocol: sw.protocol,
      port: sw.port,
      credential_id: sw.credential_id,
      notes: sw.notes ?? '',
    });
  }
  function cancel() {
    setDraft(null);
    setShowNewCred(false);
  }
  async function save() {
    if (!draft) return;
    let credId = draft.credential_id;
    if (showNewCred) {
      const created = await createCred.mutateAsync(newCred);
      credId = created.id;
    }
    if (credId === null) return;
    const payload = { name: draft.name, ip: draft.ip, protocol: draft.protocol, port: draft.port, credential_id: credId, notes: draft.notes };
    if (draft.id === null) {
      create.mutate(payload, { onSuccess: () => cancel() });
    } else {
      update.mutate({ id: draft.id, input: payload }, { onSuccess: () => cancel() });
    }
  }

  return (
    <main>
      <header className="page-header">
        <p className="marker">/02 · INV</p>
        <h1 className="headline">Inventory, sharpened for operators.</h1>
        <div className="page-actions">
          <label>
            <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
            Show inactive
          </label>
          <button onClick={startAdd} disabled={draft !== null}>+ Add switch</button>
        </div>
      </header>

      <table className="data-table">
        <thead>
          <tr><th>Name</th><th>Host</th><th>Protocol</th><th>Port</th><th>Credential</th><th>State</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {draft && draft.id === null && (
            <DraftRow
              draft={draft} setDraft={setDraft}
              credentials={credentials}
              showNewCred={showNewCred} setShowNewCred={setShowNewCred}
              newCred={newCred} setNewCred={setNewCred}
              onSave={save} onCancel={cancel}
            />
          )}
          {visible.map((sw) =>
            draft && draft.id === sw.id ? (
              <DraftRow
                key={sw.id}
                draft={draft} setDraft={setDraft}
                credentials={credentials}
                showNewCred={showNewCred} setShowNewCred={setShowNewCred}
                newCred={newCred} setNewCred={setNewCred}
                onSave={save} onCancel={cancel}
              />
            ) : (
              <tr key={sw.id} data-state={sw.is_active ? 'active' : 'inactive'}>
                <td>{sw.name} {!sw.is_active && <span className="badge badge-inactive">INACTIVE</span>}</td>
                <td>{sw.ip}</td>
                <td>{sw.protocol}</td>
                <td>{sw.port}</td>
                <td>{credentials.find((c) => c.id === sw.credential_id)?.name ?? '—'}</td>
                <td>{sw.is_active ? 'active' : 'inactive'}</td>
                <td className="row-actions">
                  <button onClick={() => startEdit(sw)} disabled={!sw.is_active}>Edit</button>
                  {sw.is_active ? (
                    <>
                      <button onClick={() => backup.mutate(sw.id)}>Backup now</button>
                      <button onClick={() => deactivate.mutate(sw.id)}>Deactivate</button>
                    </>
                  ) : (
                    <>
                      <button onClick={() => activate.mutate(sw.id)}>Activate</button>
                      <button
                        onClick={() => {
                          if (window.confirm(`Permanently delete ${sw.name}? Backup files will be preserved.`)) {
                            remove.mutate(sw.id);
                          }
                        }}
                      >
                        Delete
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </main>
  );
}

function DraftRow(props: {
  draft: DraftSwitch;
  setDraft: (d: DraftSwitch) => void;
  credentials: { id: number; name: string }[];
  showNewCred: boolean;
  setShowNewCred: (v: boolean) => void;
  newCred: { name: string; username: string; password: string; enable_password: string };
  setNewCred: (v: { name: string; username: string; password: string; enable_password: string }) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const { draft, setDraft, credentials, showNewCred, setShowNewCred, newCred, setNewCred, onSave, onCancel } = props;
  return (
    <>
      <tr className="draft-row">
        <td><input placeholder="Name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
        <td><input placeholder="Host/IP" value={draft.ip} onChange={(e) => setDraft({ ...draft, ip: e.target.value })} /></td>
        <td>
          <select value={draft.protocol} onChange={(e) => setDraft({ ...draft, protocol: e.target.value, port: DEFAULT_PORT[e.target.value] ?? draft.port })}>
            {PROTOCOLS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </td>
        <td><input type="number" value={draft.port} min={1} max={65535} onChange={(e) => setDraft({ ...draft, port: Number(e.target.value) })} /></td>
        <td>
          <CredentialCombo
            credentials={credentials as never}
            value={draft.credential_id}
            onChange={(id) => { setDraft({ ...draft, credential_id: id }); setShowNewCred(false); }}
            onCreateNew={() => setShowNewCred(true)}
          />
        </td>
        <td>—</td>
        <td className="row-actions">
          <button onClick={onSave}>Save</button>
          <button onClick={onCancel}>Cancel</button>
        </td>
      </tr>
      {showNewCred && (
        <tr className="draft-subrow">
          <td colSpan={7}>
            <fieldset>
              <legend>New credential</legend>
              <input placeholder="Name" value={newCred.name} onChange={(e) => setNewCred({ ...newCred, name: e.target.value })} />
              <input placeholder="Username" value={newCred.username} onChange={(e) => setNewCred({ ...newCred, username: e.target.value })} />
              <input type="password" placeholder="Password" value={newCred.password} onChange={(e) => setNewCred({ ...newCred, password: e.target.value })} />
              <input type="password" placeholder="Enable password (optional)" value={newCred.enable_password} onChange={(e) => setNewCred({ ...newCred, enable_password: e.target.value })} />
            </fieldset>
          </td>
        </tr>
      )}
    </>
  );
}
```

- [ ] **Step 4: Run tests, expect PASS.**

Run: `npm --prefix app_v4/web test -- --run src/pages/SwitchesPage.test.tsx`

- [ ] **Step 5: Commit**

```bash
git add app_v4/web/src/pages/SwitchesPage.tsx app_v4/web/src/pages/SwitchesPage.test.tsx
git commit -m "feat(switches): inline CRUD page with hybrid credential and soft-delete"
```

---

## Task 7: CredentialsPage inline CRUD

**Files:**
- Modify: `app_v4/web/src/pages/CredentialsPage.tsx`
- Modify: `app_v4/web/src/pages/CredentialsPage.test.tsx`

- [ ] **Step 1: Write failing tests**

Replace `app_v4/web/src/pages/CredentialsPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CredentialsPage } from './CredentialsPage';

const createMutate = vi.fn();
const deleteMutate = vi.fn();

vi.mock('../api/hooks', () => ({
  useCredentials: () => ({ data: [
    { id: 1, name: 'Lab admin', username: 'lab' },
  ], isLoading: false }),
  useCreateCredential: () => ({ mutate: createMutate, isPending: false }),
  useUpdateCredential: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteCredential: () => ({ mutate: deleteMutate, isPending: false }),
}));

describe('CredentialsPage', () => {
  it('opens an inline draft row on + Add credential', async () => {
    const user = userEvent.setup();
    render(<CredentialsPage />);
    await user.click(screen.getByRole('button', { name: /add credential/i }));
    expect(screen.getByPlaceholderText(/name/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/^password$/i)).toBeInTheDocument();
  });

  it('renders the secret column as masked', () => {
    render(<CredentialsPage />);
    expect(screen.getByText('••••••••')).toBeInTheDocument();
  });

  it('Delete asks for confirm and calls useDeleteCredential', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<CredentialsPage />);
    await user.click(screen.getByRole('button', { name: /delete/i }));
    expect(deleteMutate).toHaveBeenCalledWith(1);
    confirm.mockRestore();
  });
});
```

- [ ] **Step 2: Run, FAIL.**

Run: `npm --prefix app_v4/web test -- --run src/pages/CredentialsPage.test.tsx`

- [ ] **Step 3: Implement inline CRUD page**

Overwrite `app_v4/web/src/pages/CredentialsPage.tsx`:

```tsx
import { useState } from 'react';
import {
  useCreateCredential,
  useCredentials,
  useDeleteCredential,
  useUpdateCredential,
} from '../api/hooks';

interface DraftCred {
  id: number | null;
  name: string;
  username: string;
  password: string;
  enable_password: string;
}

const EMPTY: DraftCred = { id: null, name: '', username: '', password: '', enable_password: '' };

export function CredentialsPage() {
  const [draft, setDraft] = useState<DraftCred | null>(null);
  const { data: credentials = [] } = useCredentials();
  const create = useCreateCredential();
  const update = useUpdateCredential();
  const remove = useDeleteCredential();

  function startAdd() {
    setDraft({ ...EMPTY });
  }

  function startEdit(c: { id: number; name: string; username?: string }) {
    setDraft({ id: c.id, name: c.name, username: c.username ?? '', password: '', enable_password: '' });
  }

  function cancel() {
    setDraft(null);
  }

  function save() {
    if (!draft) return;
    if (draft.id === null) {
      create.mutate(
        { name: draft.name, username: draft.username, password: draft.password, enable_password: draft.enable_password || undefined },
        { onSuccess: cancel },
      );
    } else {
      // On update, only send fields that were typed (don't accidentally blank password).
      const input: Partial<DraftCred> = { name: draft.name, username: draft.username };
      if (draft.password) (input as { password: string }).password = draft.password;
      if (draft.enable_password) (input as { enable_password: string }).enable_password = draft.enable_password;
      update.mutate({ id: draft.id, input }, { onSuccess: cancel });
    }
  }

  return (
    <main>
      <header className="page-header">
        <p className="marker">/03 · CREDS</p>
        <h1 className="headline">Credentials stay write-only.</h1>
        <div className="page-actions">
          <button onClick={startAdd} disabled={draft !== null}>+ Add credential</button>
        </div>
      </header>

      <table className="data-table">
        <thead>
          <tr><th>Name</th><th>Username</th><th>Secret</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {draft && draft.id === null && (
            <DraftCredentialRow draft={draft} setDraft={setDraft} onSave={save} onCancel={cancel} isNew />
          )}
          {credentials.map((c) =>
            draft && draft.id === c.id ? (
              <DraftCredentialRow key={c.id} draft={draft} setDraft={setDraft} onSave={save} onCancel={cancel} />
            ) : (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.username ?? '—'}</td>
                <td>••••••••</td>
                <td className="row-actions">
                  <button onClick={() => startEdit(c)}>Edit</button>
                  <button
                    onClick={() => {
                      if (window.confirm(`Delete credential ${c.name}?`)) remove.mutate(c.id);
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </main>
  );
}

function DraftCredentialRow(props: {
  draft: DraftCred;
  setDraft: (d: DraftCred) => void;
  onSave: () => void;
  onCancel: () => void;
  isNew?: boolean;
}) {
  const { draft, setDraft, onSave, onCancel, isNew } = props;
  return (
    <tr className="draft-row">
      <td>
        <input
          placeholder="Name"
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        />
      </td>
      <td>
        <input
          placeholder="Username"
          value={draft.username}
          onChange={(e) => setDraft({ ...draft, username: e.target.value })}
        />
      </td>
      <td>
        <input
          type="password"
          placeholder={isNew ? 'Password' : 'Password (leave blank to keep)'}
          value={draft.password}
          onChange={(e) => setDraft({ ...draft, password: e.target.value })}
        />
        <input
          type="password"
          placeholder="Enable password (optional)"
          value={draft.enable_password}
          onChange={(e) => setDraft({ ...draft, enable_password: e.target.value })}
        />
      </td>
      <td className="row-actions">
        <button onClick={onSave} disabled={isNew && (!draft.name || !draft.username || !draft.password)}>
          Save
        </button>
        <button onClick={onCancel}>Cancel</button>
      </td>
    </tr>
  );
}
```

- [ ] **Step 4: Run tests, PASS.**

Run: `npm --prefix app_v4/web test -- --run src/pages/CredentialsPage.test.tsx`

- [ ] **Step 4: Commit**

```bash
git add app_v4/web/src/pages/CredentialsPage.tsx app_v4/web/src/pages/CredentialsPage.test.tsx
git commit -m "feat(credentials): inline CRUD page"
```

---

## Task 8: Backend rebuild + smoke

- [ ] **Step 1: Run full backend suite**

Run: `python -m pytest app_v4/tests/ -q`
Expected: all green.

- [ ] **Step 2: Run web suite + build**

Run: `npm --prefix app_v4/web test -- --run && npm --prefix app_v4/web run build`
Expected: green + build OK.

- [ ] **Step 3: Rebuild PyInstaller**

Run: `powershell -ExecutionPolicy Bypass -File installer/v4/build_app.ps1 -SkipWebBuild`
Expected: `==> Build OK`.
